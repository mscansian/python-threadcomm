import sys, threading, socket, time
from Queue import Queue
from select import select

class ThreadComm():
    _port = None
    _sharedSecret = None
    _serverExit = False
    
    mode = None
    thread = None
    messages = None
    socket = None
    ready = False
    connected = False
    
    def __init__(self, port, sharedSecret):
        self._port = port
        self._sharedSecret = sharedSecret
        self.messages = Queue()
        
        #Connect and send SIN
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("127.0.0.1", self._port))
            sock.send('SIN '+self._sharedSecret)
            
            #Wait for reply
            response = None
            sock.setblocking(0)
            ready = select([sock], [], [], 1)
            if ready[0]:
                response = sock.recv(1024)
        except socket.error :
            exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
            if exceptionValue[0] == 111 :
                response = None
            else:
                raise ThreadCommException("Socket returned an unknown error")
        
        if response == None:
            #Server does not exists, create one
            try:                    
                self.thread = threading.Thread(target=self.serverRun)
                self.thread.daemon = True
                self.thread.name = "ThreadComm"
                self.thread.start()
            except:
                raise ThreadCommException("Unable to create ThreadComm thread")
            self.mode = "SERVER"
        elif response == "ACK "+self._sharedSecret:
            #Server exists and it's ok
            self.mode = "CLIENT"
            self.socket = sock
            self.ready = True
            self.connected = True
        else:
            raise ThreadCommException("Server returned an unknown response")
    
    def serverRun(self):
        #Start server
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", self._port))
        s.setblocking(0)
        self.ready = True
        
        #Wait for connections
        validConnection = False
        while not validConnection:
            s.listen(1)
            ready = select([s], [], [], 1)
            if ready[0]:
                conn, addr = s.accept()
                data = conn.recv(1024)
                if data == "SIN "+self._sharedSecret:
                    #Valid connection
                    conn.sendall("ACK "+self._sharedSecret)
                    self.socket = conn
                    validConnection = True
                else:
                    #Invalid connection
                    conn.close()
        
        self.connected = True
        
        #Serve
        while not self._serverExit:
            ready = select([conn], [], [], 1)
            if ready[0]:
                try:
                    data = conn.recv(1024)
                except:
                    data = ""
                
                if data <> "":
                    self.messages.put(data)
        
        #Close connection
        conn.close()
        s.shutdown(socket.SHUT_RDWR)
        s.close()
    
    def recvMsg(self):
        data = ""
        if self.mode == "CLIENT":
            while True:
                ready = select([self.socket], [], [], 1)
                if ready[0]:
                    data = self.socket.recv(1024)
                    if data == "":
                        break
                else:
                    break
                
            data = data.splitlines()
            for line in data:                 
                self.messages.put(line)
        
        try:
            message = self.messages.get(False)
            self.messages.task_done()
            return message
        except:
            return None
    
    def sendMsg(self,msg):
        if self.socket == None:
            raise ThreadCommException("Not connected!")
        self.socket.sendall(msg+"\r\n")
        
    def kill(self):
        if self.mode == "SERVER":
            self._serverExit = True
            self.thread.join()
        else:
            self.socket.close()
    
    def waitReady(self):
        while not self.ready:
            time.sleep(1)
            
    def waitConnected(self):
        while not self.connected:
            time.sleep(1)
            

class ThreadCommException(Exception):
    def __init__(self, value):
        self.value = value
    
    def __str__(self):
        return repr(self.value)