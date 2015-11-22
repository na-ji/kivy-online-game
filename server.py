# -*- coding: utf-8 -*-

from socket import *

import json

import time
from threading import Thread

thread = None

# Service de type Thread permettant une écoute des nouvelles connexions clientes
class ListenerConnection(Thread):

    # Constructeur permettant l'initialisation des attributs
    def __init__(self, port):
        Thread.__init__(self)
        self.port = port
        self.clients = dict()
        self.sock = None
        self.id_client = 0

    # Fonction permettant l'execution du thread
    def run(self):
        print("--Listener thread running--\n")
        sock = socket(AF_INET, SOCK_STREAM)
        sock.bind(("", self.port))
        while True:

            sock.listen(9999) #Fonction permettant de fixer le nombre maximal de clients connectés à 9999
            client, address = sock.accept() # Fonction bloquante attendant une nouvelle connexion
            self.clients[address] = [client, Player(self.id_client)] # Le nouveau client est ajouté au dictionnaire des clients, on crée un player pour chaque client
            self.id_client += 1
            print "{} connected".format( address )

            # Broadcast la nouvelle connexion d'un client à tous les clients déjà connectés
            for index, address2 in enumerate(self.clients.keys()):
                if address != address2:
                    self.clients[address2][0].send(str(self.clients[address][1]) + "|")
                    self.clients[address][0].send(str(self.clients[address2][1]) + "|")

            listenerMessage = ListenerMessage(address = address) # On associe un nouveau thread au client récemment connecté
            listenerMessage.start()


# Service de type Thread permettant une écoute de son client associé et de broadcaster tout changement d'état.
class ListenerMessage(Thread):
    address = None

     # Constructeur permettant l'initialisation des attributs
    def __init__(self, address):
        Thread.__init__(self)
        self.address = address

   # Fonction permettant l'execution du thread
    def run(self):
        print "-- {} thread running --\n".format(self.address)
        keepRunning = True
        # Tant que le client est connecté, on rentre dans la boucle
        while keepRunning:

            # On essaye de communiquer avec celui ci
            try : 
                listenerConnection.clients[self.address][0].send("[]|") 
            # Dans le cas où la communication ne s'effectue pas, on supprime le client. 
            except : 
                print "Le client {} est deconnecte ".format(self.address)
                if self.address in listenerConnection.clients:
                    del listenerConnection.clients[self.address] 
                keepRunning = False
            # Si la communication est bien établie, le processus continue son execution.
            finally : 
                # Si le client est bien dans le dictionnaires de clients
                if self.address in listenerConnection.clients:
                    message     = listenerConnection.clients[self.address][0].recv(2048) # On recoit des informations du client. 
                    listMessage = json.loads(message) # On sérialise la donnée String avec la librairie JSON 
                    listenerConnection.clients[self.address][1].update(listMessage) # On met à jour les attributs de l'objet player

                    print(u"Message received from {} : {}".format(self.address, message))

                    # Si on recoit une donnée de déconnexion, on déconnecte le client. 
                    if listMessage[0] == 99 and listMessage[1] == 99:
                        print(u"Deconnecting {}".format(self.address))
                        for index, address in enumerate(listenerConnection.clients.keys()):
                            if  listenerConnection.clients[address][0] != listenerConnection.clients[self.address][0]:
                                listenerConnection.clients[address][0].send(json.dumps([listenerConnection.clients[self.address][1].id_client, 99, 99, "down"]) + "|")
                        del listenerConnection.clients[self.address]
                    # Sinon on envoit l'information à tous les clients connectés. 
                    else : 
                        for index, address in enumerate(listenerConnection.clients.keys()):
                            if  listenerConnection.clients[address][0] == listenerConnection.clients[self.address][0]:
                                pass
                            else : 
                                if len(message) > 0:
                                    new_message = json.loads(message)
                                    new_message.insert(0, listenerConnection.clients[self.address][1].id_client)
                                    listenerConnection.clients[address][0].send(json.dumps(new_message) + "|")

# Classe permettant de définir un objet player associé à un client. Il est composée de plusieurs variables. Notamment la position, la direction et l'identifiant. 
class Player : 
    def __init__(self,id_client):
        self.x = 0
        self.y = 0
        self.direction = "down"
        self.position = (self.x,self.y)
        self.id_client = id_client

    def __str__(self):
        return json.dumps([self.id_client, self.x, self.y, self.direction])

    # Service permettant de mettre à jour les variables de positions et de direction suite à la réception d'un changement d'état.
    def update(self, listMessage):
        self.x         = listMessage[0]
        self.y         = listMessage[1]
        self.direction = listMessage[2]
        

if __name__ == '__main__':

    listenerConnection = ListenerConnection(8004)
    listenerConnection.start()
