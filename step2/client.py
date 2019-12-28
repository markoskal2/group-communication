import socket
import sys
import threading
import os
import struct
import errno
import time
import queue
import random
from socketserver import ThreadingMixIn

SIZES = { 'bufferSize': 20, 'maxClients':20, 'size':1, 'msgChat':20, 'msgInfo':5}
TYPES = { 'chat':0,'people':1,'connected':2}

class Service():
    def __init__(self):
        self.Dict = {}
        self.dirIpAddr = ""
        self.dirPort = 0
        self.BUFFER_SIZE = 2048
        self.MSG = 40
        self.conn = None
        self.groups = {}
        self.notAcked = {}
        self.groupQueues = {}
        self.buffer = {}
        self.localUsers = {}
        self.pending = {}
        self.toSend = {}
        self.count = 0
        self.paused2 = False
        self.pause_cond2 = threading.Condition(threading.Lock())
        self.paused = False
        self.pause_cond = threading.Condition(threading.Lock())
        self.send = None
        self.recv = None
        self.senderQ = queue.Queue(maxsize=1)
        self.receiveQ = queue.Queue(maxsize=1)


    def connectToDirService(self, IP, PORT):
        tcpCon = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcpCon.connect((IP, PORT))
        return tcpCon

    def grp_setDir(self, dirIpAddr, dirPort):
        self.dirIpAddr = dirIpAddr
        self.dirPort = dirPort
        if self.conn is not None:
            #kill previous connection and make new one after
            print("lol")



        self.conn = self.connectToDirService(self.dirIpAddr, self.dirPort)
        self.send = threading.Thread(target=self.sendMsgTCP)
        self.send.start()
        self.recv = threading.Thread(target=self.receiveMsgTCP)
        self.recv.start()

    def grp_join(self, grpIpAddr, grpPort, name):
        # send join request to server
        groupname = grpIpAddr+":"+str(grpPort)
        self.senderQ.put("join"+":"+grpIpAddr+":"+str(grpPort)+":"+name)
        answer = self.receiveQ.get(block=True) #wait for OK from server
        if answer[0] == "notaccepted":
            return ""

        self.startMulticast(grpIpAddr,grpPort)
        return groupname+":"+name

    def sendMsgTCP(self):

        while True:
            data = self.senderQ.get(block=True)
            MESSAGE = (data+"~")
            self.conn.send(MESSAGE.encode())

    def join(self):
        self.send.join()
        self.recv.join()

    def receiveMsgTCP(self):

        while True:
            # get response
            data=""
            while True:
                character = self.conn.recv(1)
                character=character.decode()
                if(character=="~"):
                    break
                data = data + character
            fields = data.split(":")

            print(fields)
            #DETAILS ABOUT GROUP
            if fields[0] == "joined":
                groupname = fields[1] +":"+ fields[2]
                username = fields[3]
                self.groups[groupname]=self.groups[groupname] + [username]
                for k ,v in  self.localUsers.items():
                    if v[0] == groupname :
                        self.localUsers[k] = (groupname, self.localUsers[k][1] + [0])
                        user = k
                i=0
                for k in self.groups[groupname]:
                    u = k.split("/")[0]
                    if u == user.split("/")[0]:
                        MESSAGE = "info"+":"+groupname+":"+u+":"+str(self.localUsers[user][1][i])
                        break
                    i=i+1
                print(MESSAGE)
                self.senderQ.put(MESSAGE)
                #print(username + " joined group: "+ groupname)

            elif fields[0]=="left":
                groupname = fields[1] +":"+ fields[2]
                username = fields[3]
                user = username.split("/")[0]
                pos = 0
                for u in self.groups[groupname]:
                    if username==u:
                        break
                    pos = pos + 1
                i=0
                for value,usersArr in  self.notAcked[groupname]:
                    [n, ack, t, m] = self.decodeMessage(value)
                    t.pop(pos) #delete this users timestamp
                    value = self.encodeMessage(n,ack,t,m)
                    for u in usersArr:
                        # temp = u.split("/")[0]
                        print (u)
                        print (message)
                        if u == username:
                            continue
                        newU.append(u)
                    self.notAcked[groupname][i]=(value, newU) 
                    i=i+1
                for k,v in self.localUsers.items():
                    if v[0] == groupname:
                        newTimestamp = v[0].pop(pos)
                        self.localUsers[k]=(groupname,newTimestamp)
                self.delete(self.groups,groupname,username)
               
            #ANSWER TO REQUEST JOIN/LEAVE
            elif fields[0]=="accept":
                #print()
                groupname = fields[2]+":"+fields[3]
                if fields[1]=="join":
                    users=[]
                    i=0
                    for f in range(4,len(fields)-1):
                        user = fields[f]
                        #print(user)

                        users.append(user)

                    print(fields[len(fields)-1])
                    print(users)
                    timestamp = [int(x) for x in fields[len(fields)-1].split(",") if x != "*" and x !=""]
                    self.groups[groupname]=[]
                    self.buffer[groupname]=[]
                    self.groups[groupname]=self.groups[groupname]+users

                    self.localUsers[user] = (groupname, timestamp + [0])
                    print (self.localUsers)
                    if groupname not in self.notAcked.keys():
                        self.notAcked[groupname]=[]
                    
                else:
                    self.delete(self.groups,groupname,fields[4])
                    entries = {item for item in self.groups[groupname] if item in self.localUsers.keys()}
                    if entries == {}:
                        self.delete(self.groups,groupname)

                self.receiveQ.put(fields)
            elif fields[0]=='notaccepted':
                #print (fields)
                self.receiveQ.put(fields)

    def startMulticast(self,ip,port,name=None):

        addrinfo = socket.getaddrinfo(ip, port)[0]

        # s = socket.socket(addrinfo[0], socket.SOCK_DGRAM)
        s = socket.socket(addrinfo[0], socket.SOCK_DGRAM)

        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        socketSend = s
        socketReceive = s


        socketReceive.bind(('', port))

        #print(addrinfo)
        # group_bin = socket.inet_pton(addrinfo[0], addrinfo[4][0])
        group_bin = socket.inet_aton(addrinfo[4][0])
        # iface = socket.inet_aton('192.168.1.9')
        # Join group
        mreq = group_bin + struct.pack('=I', socket.INADDR_ANY) # + iface
        socketReceive.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        # Set Time-to-live (optional)
        #MYTTL = 1 , increase to reach other networks
        ttl_bin = struct.pack('@i', 1)
        socketSend.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl_bin)
        groupname= ip+":"+str(port)
        if groupname not in self.groupQueues.keys():
            q = queue.Queue()
            self.groupQueues[groupname]=q
            sender = threading.Thread(target = self.sendMulticast , args=(socketSend, ip, port, q, ))
            sender.start()

            receiver = threading.Thread(target = self.receiveMulticast , args=(socketReceive, ip, port, ))
            receiver.start()
            
            ackhandler = threading.Thread(target = self.ackHandler, args = (socketSend, ip, port, ))
            ackhandler.start()


    def ackHandler(self,send,ip,port):

        groupname=ip+":"+str(port)
        count=10
        while True:
            dynamicSleep = (len(self.notAcked[groupname])+1) * count
            print("sleep for " +str(dynamicSleep)+ " seconds")
            time.sleep(dynamicSleep)
            if groupname in self.notAcked.keys():
                for x,y in self.notAcked[groupname]:
                    print("Not yet Acknowlegded by:")
                    print(y)
                    send.sendto(x.encode(),(ip,port))
                    count = count * 2
                else:
                    count = 5
            count = count + 1


    def sendMulticast(self,conn,ip,port,q):
        
        groupname=ip+":"+str(port)
        count=0

        while True:
            (name, ack, timestampV, data) = q.get(block=True)
            
            if ack == True:
                print("~Send ack~")
                data = self.encodeMessage(name,ack,timestampV,data)
                conn.sendto(data.encode(),(ip,port))
                continue
            # data = input("Enter something:")
            print("sending")
            print(data)

            # data = str(count) + ":" + data
            i=0
            for x, y in self.localUsers.items():
                #print (x.split("/")[0])
                #print (y)
                if x.split("/")[0] == name and y[0] == groupname:
                    timestampV= y[1]
                    break
                i=i+1
            pos=0
            for x in timestampV:
                if pos==i:
                    timestampV[i]=count
                    count=count+1
                    break
                pos = pos +1
            data = self.encodeMessage(name, ack, timestampV, data)

            conn.sendto(data.encode(),(ip,port))
            self.notAcked[groupname] = self.notAcked[groupname] + [(data, self.groups[groupname])] 
            # count = count + 1

            # MESSAGE = input("Enter something:")
            # conn.sendto(MESSAGE.encode(),(ip,port))
            # # time.sleep(1)

    def encodeMessage(self, name, ack, timestamp, message):
        timestampString=""
        for k in timestamp:
            timestampString=timestampString+str(k)+";"
        timestampString = timestampString[:-1]

        #print("Send message ")
        if ack == True:
            ack = int(1)
        else:
            ack = int(0)
        #print(name+":"+str(ack)+":"+timestampString+":"+message)
        return name+":"+str(ack)+":"+timestampString+":"+message

    def decodeMessage(self, message, clean=1):
        [name,ack,timestamp,message]=message.split(":",3)

        if clean == 1:
            while message[-1:] == '\0': message = message[:-1]

        name = str(name)
        ack=int(ack)
        if ack == 1:
            ack = True
        else:
            ack = False
        #print("Decode Message")
        #print(name+":"+str(ack)+":"+timestamp+":"+message)
        # timestamp = timestamp.split(";")
        timestamp = [int(n) for n in timestamp.split(";")]

        return [name,ack,timestamp,message]

    def receiveMulticast(self, conn, ip, port):
        # Loop, #printing any data we receive
        groupname = ip+":"+str(port)
        while True:
            data, sender = conn.recvfrom(self.BUFFER_SIZE)
            data = data.decode()

            [name, ack, timestampV, message] = self.decodeMessage(data)

            if ack==True and (name+"/"+str(sender[0]) not in self.localUsers.keys()):
                print("Received foreign ack ")
                print("MULTICAST MESSAGE:")
                print("name: "+name+" ack: "+ str(ack)+" message: "+message)
                print(timestampV)
                continue

            print("MULTICAST MESSAGE:")

            print("name:"+name+" ack:"+ str(ack)+" message:"+message)
            print(timestampV)
            counter = 0
            i=0
            print(self.groups[groupname])
            for user in self.groups[groupname]:

                info = user.split("/")
                print(user)
                if info[0] == name:

                    if ack==True:
                        y=0
                        for value,usersArr in  self.notAcked[groupname]:
                            [n, ack, t, m] = self.decodeMessage(value)
                            print("TIMESTAMP: ")
                            print(t)
                            print(timestampV)
                            print("___________")
                            if t == timestampV:
                                newU=[]
                                for u in usersArr:
                                    print (u)
                                    print (message)
                                    if (u) == message:
                                        continue
                                    newU.append(u)

                                print(self.notAcked[groupname][y])
                                if newU==[]:
                                    self.notAcked[groupname].pop(y)
                                else:
                                    self.notAcked[groupname][y]=(self.notAcked[groupname][y][0], newU)
                                break
                            y=y+1
                    else:
                        flag = True

                        print(i)
                        for k ,v in self.localUsers.items():
                            if v[0] == groupname and v[1][i] > timestampV[i]:
                                flag=False
                                break

                        print("Send ack")
                        for x,y in self.localUsers.items():
                            if y[0]==groupname:
                                self.groupQueues[groupname].put((name, True,timestampV,x))
                                break

                        if flag==True:
                            # send ack
                            self.buffer[groupname].append((name,timestampV,message))
                            self.update_queue(groupname)

                i = i + 1


    def delete(self,dictionary,key,value=None,num=None):
        if value == None:
            del dictionary[key]
        if num!=None:
            dictionary[key] = { item for item in dictionary[key] if item[num] != value }
        else:
            dictionary[key] = { item for item in dictionary[key] if item != value }

    def exists(self,source,k,elem=None,num=None):
        
        for key, value in source.items():
            #print (key)
            if key == k:
                if elem !=None:
                    for i in value:
                        if num == None and i == elem:
                            return 3
                        elif num != None and i[num] == elem:
                            return 3
                    return 2
                return 1
        return 0

    def update_queue(self,groupname):

        while True:
            buffer_queue = []
            to_remove = []
            for k,v in self.localUsers.items():

                if v[0] == groupname:
                    my_timestamp = v[1]

            #print("messages in buffer")
            for name, timestampV, message in self.buffer[groupname]:
                y=0
                for n in  self.groups[groupname]:
                    if n.split("/")[0] == name:
                        break
                    y = y + 1
                remove = True
                if timestampV[y] != my_timestamp[y]:
                    remove = False
                else:
                    for i in range(len(timestampV)):
                        if timestampV[i] > my_timestamp[i]:
                            remove = False
                if not remove:
                    buffer_queue.append((name, timestampV, message))
                else:
                    to_remove.append((name, y, timestampV, message))
            for name, y, timestampV, message in to_remove:
                my_timestamp[y] += 1
                print("***************SUCCESS****************")
                print(name+" said " + message)
            
            for k,v in self.localUsers.items():
                if v[0] == groupname:
                    self.localUsers[k] = (self.localUsers[k][0], my_timestamp)

            self.buffer[groupname] = buffer_queue

            if not to_remove:
                break


    def grp_leave(self, gsocket):
        if gsocket is None:
            #print("Wrong gsocket")
            return -1
        #leave this certain group???????
        fields = gsocket.split(":")
        groupname = fields[0] + ":" + fields[1]
        username = fields[2]
        if self.exists(self.groups,groupname,username) == 3:
            #print("Wrong gsocket")
            return -1
        MESSAGE = "leave:" + gsocket
        self.senderQ.put(MESSAGE)
        self.receiveQ.get(block=True)

        return 0

    def close(self):
        self.recv.kill()
        self.send.kill()

    def grp_info(self):
        for key,value in self.groups.items():
            #print("Group: "+ key+"\nMembers:")
            for v in value:
                print(v)

    def grp_send(self, gsocket, MESSAGE, length):
        if length > self.BUFFER_SIZE:
            #print("Message too large")
            return -1
        if gsocket is None:
            #print("Wrong gsocket")
            return -1

        fields = gsocket.split(":")
        groupname = fields[0] + ":" + fields[1]
        username = fields[2]
        if self.exists(self.groups,groupname,username) == 3:
            #print("Wrong gsocket")
            return -1

        self.groupQueues[groupname].put((username, False, None, MESSAGE[0:length]))

    def grp_recv(self, gsocket, mtype, MESSAGE, length):
        if gsocket not in sockets:
            #print("eisai malakas")
            return (-1)
        if mtype == "chat":
            print("Chat not ready for use")
        else:
            MESSAGE = self.conn.recv(length)


gsocket=None
newTest = Service()
newTest.grp_setDir("192.168.1.9",8888)

while True:
    MESSAGE = input("Enter command:\n")

    if MESSAGE == 'exit':
        break
    elif MESSAGE == 'join':
        ipaddr = input("Enter ipaddress:\n")
        port = input("Enter port:\n")
        username = input("Enter username:\n")
        gsocket = newTest.grp_join(ipaddr,int(port),username)
    elif MESSAGE == 'leave':
        newTest.grp_leave(gsocket)
    elif MESSAGE == 'info':
        newTest.grp_info()
    elif MESSAGE == 'send':
        MESSAGE = input("what to send?")
        newTest.grp_send(gsocket,MESSAGE,len(MESSAGE))
newTest.join()