import socket
import sys
import threading
import os
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
        self.BUFFER_SIZE = 1024
        self.MSG = 40
        self.conn = None
        self.groups = {}
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
        self.senderQ = queue.Queue()
        self.receiveQ = queue.Queue()


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
        # self.toSend.update({self.count:['join',grpIpAddr,grpPort,name]})
        self.senderQ.put("join"+":"+grpIpAddr+":"+str(grpPort)+":"+name)
        answer = self.receiveQ.get(block=True) #wait for OK from server
        if answer[0] == "notaccepted":
            return ""
        # self.groups.update({groupname:[]})
        # MESSAGE = "join:"+ str(grpIpAddr) + ":" + str(grpPort) +":" +"name"+"~"
        return groupname+":"+name

    def sendMsgTCP(self):

        while True:
            data = self.senderQ.get(block=True)
            print (data)
            MESSAGE = (data+"~")
            self.conn.send(MESSAGE.encode())
            # self.pending.update({key:data})

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
                self.groups[groupname]=self.groups[groupname]+[username]
                # temp = []
                # for t in self.groups[groupname]:
                #     temp.append(t)
                # temp.append(username)
                # self.groups.update({groupname:temp})
                
                print(username + " joined group: "+ groupname)

            elif fields[0]=="left":
                groupname = fields[1] +":"+ fields[2]
                username = fields[3]
                print (self.groups[groupname])
                self.delete(self.groups,groupname,username)
                # self.groups[groupname] = { item for item in self.groups[groupname] if item != username }
                print (self.groups[groupname])

            #ANSWER TO REQUEST JOIN/LEAVE
            elif fields[0]=="accept":
                print()
                groupname = fields[2]+":"+fields[3]
                if fields[1]=="join":
                    users=[]
                    i=0
                    for f in fields:
                        if i <= 3:
                            i=i+1
                            continue
                        user=f
                        print(user)

                        users.append(user)
                        # if groupname not in self.groups:
                        #     self.groups.update({groupname:[f, ]})
                        # else:
                        #     self.groups[groupname].append(f)
                    self.groups.update({groupname: users })
                    self.localUsers.update({user: groupname })
                    print("Users: ")
                    print(users)
                    fields.pop(0)
                    
                else:
                    # if len(self.groups[groupname])==1:
                    #     del self.groups[groupname]
                    # else: 
                    self.delete(self.groups,groupname,fields[4])

                    print (self.groups[groupname])
                    entries = {item for item in self.groups[groupname] if item in self.localUsers.keys()}
                    if entries == {}:
                        self.delete(self.groups,groupname)

                self.receiveQ.put(fields)
            elif fields[0]=='notaccepted':
                print (fields)
                self.receiveQ.put(fields)

    def startMulticast(self,ip,port,name=None):

        addrinfo = socket.getaddrinfo(ip, port)[0]

        s = socket.socket(addrinfo[0], socket.SOCK_DGRAM)

        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)


        s.bind(('', port))


        group_bin = socket.inet_pton(addrinfo[0], addrinfo[4][0])
        # Join group
        mreq = group_bin + struct.pack('=I', socket.INADDR_ANY)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        # Set Time-to-live (optional)
        ttl_bin = struct.pack('@i', MYTTL)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl_bin)
        
        sender = threading.Thread(target = self.sendMulticast , args=(s,))
        sender.start()

        receiver = threading.Thread(target = self.receiveMulticast , args=(s,))
        receiver.start()
        receiver.join()
        sender.join()
        # while True:
        #     data = repr(time.time())
        #     print (data)
        #     s.sendto(data.encode(), (addrinfo[4][0], MYPORT))
        #     time.sleep(1)


    def sendMulticast(self,conn):
        while True:
            data = repr(time.time())
            print (data)
            conn.sendto(data.encode())
            time.sleep(1)



    def receiveMulticast(self,conn):
        # Loop, printing any data we receive
        while True:
            data, sender = conn.recvfrom(1024)
            while data[-1:] == '\0': data = data[:-1] # Strip trailing \0's
            print (str(sender) + '  ' + data.decode())

    def delete(self,dictionary,key,value=None):
        if value == None:
            del dictionary[key]
        dictionary[key] = { item for item in dictionary[key] if item != value }

    def exists(self,source,k,elem=None):
        
        for key, value in source.items():
            if key == k:
                if elem !=None:
                    for i in value:
                        if i == elem:
                            return True
                return True
        return False
            
    def grp_leave(self, gsocket):
        if gsocket is None:
            print("lol")
            return -1
        #leave this certain group???????
        fields = gsocket.split(":")
        groupname = fields[0] + ":" + fields[1]
        username = fields[2]
        if not self.exists(self.groups,groupname,username):
            print("Wrong gsocket")
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
            print("Group: "+ key+"\nMembers:")
            for v in value:
                print(v)

    def grp_send(self, gsocket, MESSAGE, length):
        print("OK")
    def grp_recv(self, gsocket, mtype, MESSAGE, length):
        if gsocket not in sockets:
            print("eisai malakas")
            return (-1)
        if mtype == "chat":
            print("Chat not ready for use")
        else:
            MESSAGE = self.conn.recv(length)


gsocket=None
newTest = Service()
newTest.grp_setDir("127.0.0.1",8888)
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
    elif MESSAGE == 'chat':
        newTest.startMulticast("230.1.1.1",50000)
newTest.join()