import logging

logger = logging.getLogger(__name__)


class Plugin(object):
    def __init__(
        self,
        client,
        compromised_resource,
        dry_run=False
    ):

        self.client = client
        self.compromised_resource = compromised_resource
        self.compromise_type = compromised_resource['compromise_type']
        self.examiner_cidr_range = compromised_resource['examiner_cidr_range']
        self.dry_run = dry_run

        self.setup()

    def setup(self):
        sg = self.__create_isolation_security_group()
        if self.exists is not True:
            acl = self.__create_network_acl()
            self.__add_network_acl_entries(acl)
            self.__add_security_group_to_instance(sg)

        """Conditions that can not be dry_run"""
        if self.dry_run is False:
            self.__revoke_egress(sg)
            self.__add_security_group_to_instance(sg)

    def validate(self):
        """Validate that the instance is in fact isolated"""
        if self.sg_name is not None:
            return True
        else:
            return False

    def __create_isolation_security_group(self):
        try:
            security_group_result = self.client.create_security_group(
                DryRun=self.dry_run,
                GroupName=self.__generate_security_group_name(),
                Description="ThreatResponse Isolation Security Group",
                VpcId=self.compromised_resource['vpc_id'],

            )

            self.exists = False

        except Exception:
            logger.info(
                "Security group already exists. Attaching existing SG."
            )
            self.exists = True
            security_group_result = self.client.describe_security_groups(
                DryRun=self.dry_run,
                GroupNames=[
                    self.__generate_security_group_name()
                ]
            )['SecurityGroups'][0]
        return security_group_result['GroupId']

    def __revoke_egress(self, group_id):
        result = self.client.revoke_security_group_egress(
            DryRun=self.dry_run,
            GroupId=group_id,
            IpPermissions=[
                {
                    'IpProtocol': '-1',
                    'FromPort': -1,
                    'ToPort': -1,
                },
            ]
        )
        return result

    def __generate_security_group_name(self):
        sg_name = "isolation-sg-{case_number}-{instance}".format(
            case_number=self.compromised_resource['case_number'],
            instance=self.compromised_resource['instance_id']
        )
        self.sg_name = sg_name
        return sg_name

    def __add_security_group_to_instance(self, group_id):
        try:
            self.client.modify_instance_attribute(
                DryRun=self.dry_run,
                InstanceId=self.compromised_resource['instance_id'],
                Groups=[
                    group_id,
                ],
            )
            return True
        except Exception:
            return False

    def __create_network_acl(self):
        try:
            response = self.client.create_network_acl(
                DryRun=self.dry_run,
                VpcId=self.compromised_resource['vpc_id'],
            )
            return response['NetworkAcl']['NetworkAclId']
        except Exception as e:
            try:
                if e.response['Error']['Message'] == """
                Request would have succeeded, but DryRun flag is set.
                """:
                    return None
            except Exception as e:
                raise e

    def __add_network_acl_entries(self, acl_id):
        try:
            self.client.create_network_acl_entry(
                DryRun=self.dry_run,
                NetworkAclId=acl_id,
                RuleNumber=1337,
                Protocol='-1',
                RuleAction='deny',
                Egress=True,
                CidrBlock="0.0.0.0/0"
            )
            return True
        except Exception as e:
            try:
                if e.response['Error']['Message'] == """
                Request would have succeeded, but DryRun flag is set.
                """:
                    return None
            except Exception as e:
                raise e
