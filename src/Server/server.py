
import socket                   # Import socket module
#import tinys3
import boto
import boto.s3
import os,sys
import math
import boto3
import json
import threading
import base64
from boto.s3.key import Key
from scapy.all import *
import logging
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
import re

port = 6017                   # Reserve a port for your service.



AWS_ACCESS_KEY_ID = ''
AWS_SECRET_ACCESS_KEY = ''

bucket_name = 'images-test-pi1'#AWS_ACCESS_KEY_ID.lower() + '-dump'
s3_connection = boto.connect_s3(AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY)
COLLECTION = "photocollection1"

Faceid=""
sensordata=""

sensorvalue = [100]
buckets = s3_connection.create_bucket(bucket_name,
   location=boto.s3.connection.Location.DEFAULT)

region="us-east-1"
rekognition = boto3.client("rekognition", region,aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY        )

answer = "Nothing"
data_received = False
BUFF_SIZE = 8096 # 4 KiB
total_ip_traffic = 0
total_image_size = 0
imagecounter = 1

def recvall(sock):
   
    data = ""
    while True:
        part = sock.recv(BUFF_SIZE)
        #size = int.from_bytes(b'part', byteorder='little')
        data += part
        
        #print part
        if not part: break
            # either 0 or end of data
         #   print  'ending'
         #   break
        
    return data

FEATURES_BLACKLIST = ("Landmarks", "Emotions", "Pose", "Quality", "BoundingBox", "Confidence")

with open('m1.jpg', 'rb') as image:
         response = rekognition.index_faces(Image={'Bytes': image.read(),}, CollectionId=COLLECTION,ExternalImageId = 'Marziehh2')


def detect_faces(bucket, key, attributes=['ALL'], region="us-east-1"):
    rekognition = boto3.client("rekognition", region)
    response = rekognition.detect_faces(
            Image={"S3Object": {
            "Bucket": bucket,

            "Name": key,

    }

            },

            Attributes=attributes,

        )

    return response['FaceDetails']


def search_faces_by_image(bucket, key, collection_id, threshold=80, region="us-east-1"):
        #rekognition = boto3.client("rekognition", region,aws_access_key_id=AWS_ACCESS_KEY_ID,
        #aws_secret_access_key=AWS_SECRET_ACCESS_KEY        )
        response = rekognition.search_faces_by_image(
        Image={
"S3Object": {
"Bucket": bucket,
"Name": key,
        }
        },
        CollectionId=collection_id,
        FaceMatchThreshold=threshold,
                )
        return response['FaceMatches']




def packet_callback(packet):

    global total_ip_traffic

    total_ip_traffic += packet[IP].len

    print("Packet size %s - Total: %s image: %s:" % (packet[IP].len, total_ip_traffic,  total_image_size))

def detect_labels(bucket, key, max_labels=10, min_confidence=90, region="us-east-1"):
    #rekognition = boto3.client("rekognition", region)
    response = rekognition.detect_labels(
    Image={
        "S3Object": {
        "Bucket": bucket,
        "Name": key,
        }
    },
    MaxLabels=max_labels,
    MinConfidence=min_confidence,
    )
    return response['Labels']




    #for label in detect_labels(BUCKET, KEY):
#print "{Name} - {Confidence}%".format(**label)
        
def upload_file(s3, bucketname, file_path):

        b = s3.get_bucket(bucketname)

        filename = os.path.basename(file_path)
        k = b.new_key(filename)

        mp = b.initiate_multipart_upload(filename)

        source_size = os.stat(file_path).st_size
        bytes_per_chunk = 5000*1024*1024
        chunks_count = int(math.ceil(source_size / float(bytes_per_chunk)))

        for i in range(chunks_count):
                offset = i * bytes_per_chunk
                remaining_bytes = source_size - offset
                bytes = min([bytes_per_chunk, remaining_bytes])
                part_num = i + 1

                print "uploading part " + str(part_num) + " of " + str(chunks_count)

                with open(file_path, 'r') as fp:
                        fp.seek(offset)
                        mp.upload_part_from_file(fp=fp, part_num=part_num, size=bytes)

        if len(mp.get_all_parts()) == chunks_count:
                mp.complete_upload()
                print "upload_file done"
        else:
                mp.cancel_upload()
                print "upload_file failed"
        

def process_Android_data(conn,identity,sensordata):
    print 'sending to android'
    dict = {}
    dict['identity'] = identity
    filename='image.jpg'
    with open(filename, 'r') as content_file:
        content = content_file.read()
        str = base64.b64encode(content)
    dict['image']=str
    dict['sensordata']=sensordata
    print dict['identity']
    data_string = json.dumps(dict)
    #print data_string
    strlen = len(data_string)
    print 'length'
    print strlen
    conn.send(bytes(strlen))
    print 'data'
    #print data_string
    conn.send(data_string)
    

def polling(conn):
    global answer
    #print 'polling'
    strlen = len(answer)
    print 'length'
    print strlen
    print 'answer'
    print answer
    conn.send(bytes(strlen))
    conn.send(answer)
    if data_received:
        print 'send to RPI'
    
def non_polling(conn):
    global answer
    print 'non-polling'
    
    #if answer != '':
    while True:
        if answer != 'Nothing':
            strlen = len(answer)
            print 'length'
            print strlen
            print 'answer'
            print answer
            conn.send(bytes(strlen))
            conn.send(answer)



    


def process_RPI_data(conn):
     data = recvall(conn)
     f.write(data)
     f.close()
     print 'file received'
     s3 = boto.connect_s3(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
     filepath = 'image.jpg'
     upload_file(s3, bucket_name, filepath)
     for record in search_faces_by_image(bucket_name, filepath, COLLECTION):
          face = record['Face']
          print "Matched Face ({}%)".format(record['Similarity'])
          print "  FaceId : {}".format(face['FaceId'])
          print "  ImageId : {}".format(face['ExternalImageId'])

    

def make_connection(num,conn):

    global answer
    #print("answer = %s " % answer)
    global sensordata
    global Faceid
    global total_ip_traffic
    global total_image_size
    print 'Server listening....'
    while True:
        #conn, addr = s.accept()     # Establish connection with client.
        senddict={}
        print 'Got connection from', addr
        #dentity = conn.recv(4096)
        #print('data=%s', (identity))
        #part = conn.recv(BUFF_SIZE)
        #print part
        #data = conn.recv(part)
        #size = int(part)
        # print size
        i = 0
        data=""
        part = ""
        #Faceid = ""
        while True:
            part = conn.recv(1)
            print part
            if not part.isdigit():
            #if part == '\r':
                break
            data+=part
        print data
        #if data == "":
        #    print("what is %s"% data)
        #    continue
        size = int(data)    
        print size
        #data = recvall(conn)
        print 'received'
        print data
        data = part
        print data
        #part = conn.recv(size)
        cc = 1
        while cc < size:
            part = conn.recv(1)
            #print part
            data+=part
            #print cc
            cc = cc + 1
        #print 'here'
        #print data
        #data+=part
        #print data
        
        #Faceid = ""
        # print('Server received', repr(data))
        #jsondata = data.decode('utf-8')
        #print jsondata
        dict = json.loads(data)
        print dict['identity']
        identity = dict['identity']
    
        if identity == 'rpi_sender':
            sensordata=dict['sensordata']
            print sensordata

            with open('image.jpg', 'wb') as f:
                print 'file opened'
      
                # write data to a file
                image = dict['image'].decode('base64')
                print(" Total: %s image: %s:" % ( total_ip_traffic,  total_image_size))
                total_image_size += int(dict['image_size'])
                f.write(image)
                #data = recvall(conn)
                #f.write(data)
                f.close()
                print 'file received'
                s3 = boto.connect_s3(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
                filepath = 'image.jpg'
                upload_file(s3, bucket_name, filepath)
#               detect_labels(bucket_name, '1.jpg')
                #for label in detect_labels(bucket_name, filepath):
                #    print "{Name} - {Confidence}%".format(**label)
                #image = image
                #for face in detect_faces(bucket_name, filepath):
                #    print "Face ({Confidence}%)".format(**face)
            try:
                     for record in search_faces_by_image(bucket_name, filepath, COLLECTION):
                         face = record['Face']
                         print "Matched Face ({}%)".format(record['Similarity'])
                         print "  FaceId : {}".format(face['FaceId'])
                         print "  ImageId : {}".format(face['ExternalImageId'])
                         Faceid=face['ExternalImageId']
                     if Faceid == '':
                         Faceid = 'unknown'
                            
                     print ('Faceid = %s'%Faceid)
            except:
                Faceid = 'Unknown'
                print Faceid

        elif identity == 'android':
            if dict['answer'] == 'register':
                    print ('register')
                    reg_image = dict['image'].decode('base64')
                    #print reg_image
                    reg_id = dict['reg_id']
                    print reg_id
                    register_image_collection(reg_image,reg_id)
            process_Android_data(conn,Faceid,sensordata)
            print dict['answer']
            answer =  dict['answer']
        elif identity == 'rpi_receiver':
            print 'polling'
            polling(conn)
        elif identity == 'rpi_receiver_non_polling':
            non_polling(conn)

            

           
                    
    print('Successfully get the file')
    #conn.send('Thank you for connecting')
    conn.close()


def create_collection():
    #client = boto3.client('rekognition', region_name='us-east-1')
    response = rekognition.create_collection(
    CollectionId=COLLECTION,)
    with open('1.jpg', 'rb') as image:
         response = client.index_faces(Image={'Bytes': image.read(),}, CollectionId=COLLECTION,ExternalImageId = 'Marzieh')

def register_image_collection(reg_img,reg_id):
    global imagecounter
    imagecounter = imagecounter+1
    #client = boto3.client('rekognition', region_name='us-east-1')
    #response = client.open_collection(
    #    CollectionId='photocollection',)
    imagefile = str(imagecounter)+'.jpg'
    #imagefile = 'm1.jpg'
    with open(imagefile, 'wb') as f:
                print 'file opened'

                # write data to a file                                                                                                                                                                       
                #image = dict['image'].decode('base64')
                #print(" Total: %s image: %s:" % ( total_ip_traffic,  total_image_size))
                #total_image_size += int(dict['image_size'])
                f.write(reg_img)
    print 'file saved'
    with open(imagefile, 'rb') as image:
         response = rekognition.index_faces(Image={'Bytes': image.read(),}, CollectionId=COLLECTION,ExternalImageId = reg_id)
    print 'file registered!!!'
    #response = client.index_faces(Image={'Bytes': reg_img,}, CollectionId='photocollection',ExternalImageId = reg_id)


def computeOverhead():
    sniff(filter="tcp port 6012", prn=packet_callback, iface="eth0", store=0)

    
if __name__ == "__main__":
    print 'Hello'
    #create_collection()
    s = socket.socket()             # Create a socket object                   
    print 'socket created'                                                                                                                            
    host = socket.gethostname()     # Get local machine name                                                                                                                                                
    s.bind((host, port))            # Bind to the port                                                                                                                                                      
    s.listen(5)                     # Now wait for client connection.                                                                                                                                        
    
    print 'Server listening....'
    threads = []

    t = threading.Thread(target=computeOverhead, args=())
    threads.append(t)
    #t.start()

    i = 0
    #sniff(iface="eth0",filter="tcp", prn=packet_callback, store=0)
    while True:
        conn, addr = s.accept()     # Establish connection with client.
        t = threading.Thread(target=make_connection, args=(i,conn))
        i = i + 1
        
        threads.append(t)
        t.start()
    #print response
    #bucketname = sys.argv[1]
    #filepath = sys.argv[2]
    #s3 = boto.connect_s3(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    #upload_file(s3, bucketname, filepath)
    #make_connection()
   
