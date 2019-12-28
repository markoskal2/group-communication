import socket
import threading
import queue
import time

# Multithreaded Python server : TCP Server Socket Thread Pool
class DirectoryService():
    def __init__(self, ip, port, maxClients=None):
        self.ip = ip
        self.maxClients = maxClients
        self.port = port
        self.clients=[]
        self.groups = {}
        self.users = {}
        self.connections = {}
        self.usersTimeS = {}
        print ("[+] New server socket thread started for " + ip + ":" + str(port) + " buffer size: ")

    def run(self,conn):
        q_in = queue.Queue(maxsize=0)
        q_out = queue.Queue(maxsize=0)

        tR =threading.Thread(target=self.receiveTCP, args=(conn,q_out, ))
        tR.start()

        tS =threading.Thread(target=self.sendTCP,args=(conn,q_out, ))
        tS.start()
        (ip, port)= conn.getpeername()
        connIpPort =ip+":"+str(port)
        self.connections.update({connIpPort:q_out})
        # t2.join()
        # t1.join()

    def delete(self,dictionary,key,value=None):
        if value == None:
            del dictionary[key]
        dictionary[key] = { item for item in dictionary[key] if item != value }

    def exists(self,source,k,elem=None,num=None):
        
        for key, value in source.items():
            print (key)
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

    def notifyGroup(self,groupname,username,action,error=0):
        print("Notify")
        if groupname not in self.groups:
            print("think before you act")
            return
        for attr in self.groups[groupname]:
            if username == attr[1]:
                conn = attr
                break
        ip = conn[0].split(":")[0]
        username = conn[1]
        if action =="join":
            message = "joined:"+groupname+":"+username+"/"+ip
        else:
            message = "left:"+groupname+":"+username+"/"+ip
        self.usersTimeS = {}
        users = ""
        for attr in self.groups[groupname]:
            # print("~~~"+str(attr[0]))
            if username == attr[1]:
                continue
            users=users+attr[1]+"/"+attr[0].split(":")[0]+":"
            if attr[0] in self.connections.keys():
                self.connections[attr[0]].put(message)
        giveaway=""
        if action == "join":

            while len(self.usersTimeS) < len(self.groups[groupname])-1:
                print("wait")
                print(self.usersTimeS)
                time.sleep(1)
            
            for k,v in self.usersTimeS.items():
                giveaway = giveaway + v +","
            if giveaway == "":
                giveaway="*"

        if error==0:
            users=users+username+"/"+ip

            message ="accept:"+action+":"+groupname
            if action =="join" and users != "":
                message = message +":"+users+":"+giveaway # giveaway = timestamp
            else:
                message =message+":"+username
            print("LOLED "+message)
            self.connections[conn[0]].put(message)
        

    def receiveTCP(self,conn,q_out):

        (ip, port)= conn.getpeername()
        connIpPort =ip+":"+str(port)
        try:
            while True :
                data = ""
                while True:
                    character = conn.recv(1)
                    character=character.decode()
                    if(character == "~"):
                        break
                    data = data + character
                print("Received: "+ data)
                fields=data.split(":")

                if fields[0] == 'join':

                    groupname = fields[1]+":"+fields[2] #GROUP TO ENTER
                    username = fields[3] #USERNAME
                    # print (conn.getsockname()) #own address,port
                    if self.exists(self.groups,groupname, username,1) == 3:
                        print("Username already exists")
                        q_out.put("notaccepted:"+":"+groupname+":"+username)
                        continue

                    if groupname not in self.groups.keys():
                        self.groups.update({groupname: [(connIpPort,username),]})
                    else:
                        self.groups[groupname]=self.groups[groupname]+[(connIpPort,username)]
                        # old=self.groups[groupname]

                        # old.append((connIpPort,username))
                        # self.groups[groupname] = old

                        
                    if self.exists(self.users,connIpPort) == 0:
                        self.users.update({connIpPort: [username,] })
                    else:
                        self.users[connIpPort]=self.users[connIpPort]+[username]

                    threading.Thread( target = self.notifyGroup(groupname,username,"join")).start()


                elif fields[0] == 'leave':
                    groupname = fields[1] + ":" + fields[2] #GROUP TO ENTER
                    username = fields[3] #USERNAME

                    # print (conn.getsockname()) #own address,port
                    code = self.exists(self.groups,groupname,username)
                    if code !=3 :
                        print("Username doesnt exist")
                        q_out.put("Username doesnt exists")
                    if code == 0:
                        print("Group doesnt exist")
                        q_out.put("Group doesnt exist")
                    else:
                        #q_in.put("leav"+":"+groupname+":"+username+":"+)
                        self.notifyGroup(groupname,username,"leave")

                        if len(self.groups[groupname])==1:
                            del self.groups[groupname]
                        else:
                            self.delete(self.groups,groupname,username)
                            # self.groups[groupname].pop(username)
                    #connIpPort =ip+":"+str(port)
                elif fields[0] == 'info':
                    print("YES")
                    groupname = fields[1]+":"+fields[2] #GROUP TO ENTER
                    username = fields[3] #USERNAME
                    self.usersTimeS.update({username: fields[4]})
                    # print (conn.getsockname()) #own address,port
                    # if groupname not in self.groups:
                    #     q_out.put("Wrong groupname")
                    # else:
                    #     q_out.put(self.groups[groupname])
        except BrokenPipeError:
            conn.close()
            self.brokenpipe(connIpPort)

   
    def sendTCP(self,conn,q_in):
        (ip, port)= conn.getpeername()
        connIpPort =ip+":"+str(port)
        try:

            while True:
                data = q_in.get(block=True)
                print("Send "+ str(data))
                # if not isinstance(data , str):
                #     users=""
                #     for user in data:
                #         users=users+user+":"
                #     users = users[:-1] +"~"
                #     conn.send(users.encode())
                # else:

                conn.send((data+"~").encode())
        except BrokenPipeError:
            conn.close()
            self.brokenpipe(connIpPort)

    def brokenpipe(self,connection):

        for key,value in self.groups.items():
            for f in value:
                if f[0] == connection:
                    # delete  user from group and notify others for his withdrawal
                    self.notifyGroup(key,f[1],"leave",1)
                    self.groups[key]= {item for item in self.groups[key] if item != f } 
                    break
        # also delete everything related to this connection
        # self.delete(self.users,connection)
        # self.delete(self.connections,connection)
        if connection in self.users.keys():
            del self.users[connection]
        if connection in self.connections.keys():
            del self.connections[connection]



    def main(self):

        tcpServer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcpServer.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        tcpServer.bind((self.ip, self.port))

        while True:
            tcpServer.listen(self.maxClients)
            print ("\n Waiting for connections from TCP clients...\n")
            (conn, (ip, port)) = tcpServer.accept()
            t1 = threading.Thread(target = self.run,args=(conn,))
            t1.start()
            # t2 = threading.Thread(target = self.send,args=(conn,))
            # t2.start()


if __name__ == "__main__":
    t = DirectoryService("0.0.0.0",8888,50)
    t.main()
    t.join()