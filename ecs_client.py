from collections import defaultdict
import threading
import Queue
import boto3

class EcsClient:

    def __init__(self, acct_to_assume, role_to_assume):
        self.acct_to_assume = acct_to_assume
        self.role_to_assume = role_to_assume
        boto3.setup_default_session(profile_name='default')

        self.client = boto3.client('sts')
    
    def retrieveClusterDescriptionsByArn(self, clusters):
        descriptions = self.ecs.describe_clusters(clusters=clusters)
        return dict((c['clusterArn'], c) for c in descriptions['clusters'])

    def retrieveContainersForCluster(self, cluster):
        firstTime = True
        containers = []
        while True:
            if firstTime:
                result = self.ecs.list_container_instances(cluster=cluster, maxResults=10)
            else:    
                result = self.ecs.list_container_instances(cluster=cluster, maxResults=10, nextToken=result['nextToken'])
            containers += result['containerInstanceArns']
            firstTime = False
            if 'nextToken' not in result:
                break
        if not containers:
            return containers
        descriptions = self.ecs.describe_container_instances(cluster=cluster, containerInstances=containers)['containerInstances']
        reservations = self.ec2.describe_instances(InstanceIds = map(lambda d: d['ec2InstanceId'], descriptions))['Reservations']
        instances = [item for sub in [r['Instances'] for r in reservations] for item in sub]
        byId = defaultdict(lambda: "None", [(i['InstanceId'], i) for i in instances])
        return descriptions
        #return map(lambda d: "Instance Id: " + d['ec2InstanceId'] + ", Type: " + [x for x in d['attributes'] if x['name'] == 'ecs.instance-type'][0]['value'] + ", IP address: " + ipById[d['ec2InstanceId']] , descriptions)
    
    def retrieveServicesForCluster(self, cluster):
        firstTime = True
        services = []
        while True:
            if firstTime:
                result = self.ecs.list_services(cluster=cluster, maxResults=10)
            else:    
                result = self.ecs.list_services(cluster=cluster, maxResults=10, nextToken=result['nextToken'])
            services += result['serviceArns']
            firstTime = False
            if 'nextToken' not in result:
                break
        return self.retrieveServiceDescriptionsByArn(cluster, services)
    
    def retrieveServiceDescriptionsByArn(self, cluster, services):
        descriptions = []
        threads = []
        queue = Queue.Queue()
        for i in range(0, len(services), 10):
            thread_ = threading.Thread(target = self.describe_services, args = [queue, cluster, services[i:i+10]])
            thread_.start()
            threads.append(thread_)
        
        for thread in threads:
            thread.join()
            descriptions += queue.get()

        return dict((s['serviceArn'], s) for s in descriptions)

    def describe_services(self, queue, cluster, services):
        queue.put(self.ecs.describe_services(cluster=cluster, services = services)['services'])
    
    def retrieveTasksForService(self, cluster, service):
        tasksList = self.ecs.list_tasks(cluster = cluster, serviceName = service)
        firstTime = True
        tasks = []
        while True:
            if firstTime:
                result = self.ecs.list_tasks(cluster=cluster, serviceName = service, maxResults=10)
            else:    
                result = self.ecs.list_tasks(cluster=cluster, serviceName = serviceName, maxResults=10, nextToken=result['nextToken'])
            tasks += result['taskArns']
            firstTime = False
            if 'nextToken' not in result:
                break
        return self.retrieveTaskDescriptionsByArn(cluster, tasks)
    
    def retrieveTaskDescriptionsByArn(self, cluster, tasks):
        descriptions = self.ecs.describe_tasks(cluster=cluster, tasks = tasks)['tasks']
        
        return dict((s['taskArn'], s) for s in descriptions)

    def describe_services(self, queue, cluster, services):
        queue.put(self.ecs.describe_services(cluster=cluster, services = services)['services'])

    def retrieveClusters(self):
        roleArn = "arn:aws:iam::" + self.acct_to_assume + ":role/" + self.role_to_assume
        response = self.client.assume_role( RoleArn=roleArn, RoleSessionName="stackMonitor")
         
        creds=response['Credentials']
        self.ecs = boto3.client('ecs', 
                aws_access_key_id = creds['AccessKeyId'],
                aws_secret_access_key = creds['SecretAccessKey'],
                aws_session_token = creds['SessionToken'])

        self.ec2 = boto3.client('ec2', 
                aws_access_key_id = creds['AccessKeyId'],
                aws_secret_access_key = creds['SecretAccessKey'],
                aws_session_token = creds['SessionToken'])
        arns = []
        firstTime = True
        while True:
            if firstTime:
                result = self.ecs.list_clusters(maxResults=100)
            else:    
                result = self.ecs.list_clusters(maxResults=100, nextToken=result['nextToken'])
            arns += result['clusterArns']
            firstTime = False
            if 'nextToken' not in result:
                break

        return self.retrieveClusterDescriptionsByArn(arns)
