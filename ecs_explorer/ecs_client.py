from collections import defaultdict
import itertools
import threading
import Queue
import boto3

class EcsClient(object):

    def __init__(self, role_to_assume):
        self.role_to_assume = role_to_assume
        boto3.setup_default_session(profile_name='default')
        if role_to_assume:
            self.client = boto3.client('sts')
            response = self.client.assume_role(
                RoleArn=role_to_assume, RoleSessionName="ecs_explorer")

            creds = response['Credentials']
            self.ecs = boto3.client('ecs',
                                    aws_access_key_id=creds['AccessKeyId'],
                                    aws_secret_access_key=creds['SecretAccessKey'],
                                    aws_session_token=creds['SessionToken'])

            self.ec2 = boto3.client('ec2',
                                    aws_access_key_id=creds['AccessKeyId'],
                                    aws_secret_access_key=creds['SecretAccessKey'],
                                    aws_session_token=creds['SessionToken'])
        else: 
            self.ecs = boto3.client('ecs')
            self.ec2 = boto3.client('ec2')

    def retrieve_cluster_descs(self, clusters):
        descriptions = self.ecs.describe_clusters(clusters=clusters)
        return dict((c['clusterArn'], c) for c in descriptions['clusters'])

    def retrieve_containers(self, cluster):
        first_time = True
        containers = []
        while True:
            if first_time:
                result = self.ecs.list_container_instances(
                    cluster=cluster, maxResults=10)
            else:
                result = self.ecs.list_container_instances(
                    cluster=cluster, maxResults=10, nextToken=result['nextToken'])
            containers += result['containerInstanceArns']
            first_time = False
            if 'nextToken' not in result:
                break
        if not containers:
            return dict()
        descriptions = self.ecs.describe_container_instances(
            cluster=cluster, containerInstances=containers)['containerInstances']
        descs_by_id = defaultdict(
            itertools.repeat("None").next, [(d['ec2InstanceId'], d) for d in descriptions])
        ids = [d['ec2InstanceId'] for d in descriptions]
        reservations = self.ec2.describe_instances(InstanceIds=ids)['Reservations']
        instances = [item for sub in [r['Instances']
                                      for r in reservations] for item in sub]
        by_id = defaultdict(
            lambda: "None", [(i['InstanceId'], i) for i in instances])
        return dict((key, (descs_by_id[key], by_id[key])) for key in descs_by_id.iterkeys())

    def retrieve_services(self, cluster):
        first_time = True
        services = []
        while True:
            if first_time:
                result = self.ecs.list_services(cluster=cluster, maxResults=10)
            else:
                result = self.ecs.list_services(
                    cluster=cluster, maxResults=10, nextToken=result['nextToken'])
            services += result['serviceArns']
            first_time = False
            if 'nextToken' not in result:
                break
        return self.retrieve_service_descriptions(cluster, services)

    def retrieve_service_descriptions(self, cluster, services):
        descriptions = []
        threads = []
        queue = Queue.Queue()
        for i in range(0, len(services), 10):
            thread_args = [queue, cluster, services[i:i + 10]]
            thread_ = threading.Thread(target=self.describe_services, args=thread_args)
            thread_.start()
            threads.append(thread_)

        for thread in threads:
            thread.join()
            descriptions += queue.get()

        return dict((s['serviceArn'], s) for s in descriptions)

    def retrieve_tasks(self, cluster, service):
        first_time = True
        tasks = []
        while True:
            if first_time:
                result = self.ecs.list_tasks(
                    cluster=cluster, serviceName=service, maxResults=10)
            else:
                next_token = result['nextToken']
                result = self.ecs.list_tasks(
                    cluster=cluster, serviceName=service, maxResults=10, nextToken=next_token)
            tasks += result['taskArns']
            first_time = False
            if 'nextToken' not in result:
                break
        return self.retrieve_task_descriptions(cluster, tasks)

    def retrieve_task_descriptions(self, cluster, tasks):
        descriptions = self.ecs.describe_tasks(
            cluster=cluster, tasks=tasks)['tasks']

        return dict((s['taskArn'], s) for s in descriptions)

    def describe_services(self, queue, cluster, services):
        queue.put(self.ecs.describe_services(
            cluster=cluster, services=services)['services'])

    def retrieve_clusters(self):
        arns = []
        first_time = True
        while True:
            if first_time:
                result = self.ecs.list_clusters(maxResults=100)
            else:
                result = self.ecs.list_clusters(
                    maxResults=100, nextToken=result['nextToken'])
            arns += result['clusterArns']
            first_time = False
            if 'nextToken' not in result:
                break

        return self.retrieve_cluster_descs(arns)
