#!/usr/bin/env python3
import oci
import sys
import time

INSTANCE_NAME = 'vps实例名' #你要创建的vps实例名  
SUBNET_ID = "网络->虚拟云网络->虚拟云网络详细信息->OCID" #如果是全新用户，先创建一个VNC
compartment_id="租户id"
ssh_public_key="创建的证书文本内容"
# 消息
OPERATING_SYSTEM = 'Oracle Linux'
OPERATING_SYSTEM_VERSION ='8'  
SHAPE='VM.Standard.A1.Flex'

def SendMsgByPushOver(Title,msg,html=True,token_id=0):
    """
    这里创建你的消息提醒
    """
    pass

def get_availability_domain(identity_client, compartment_id):
    list_availability_domains_response = oci.pagination.list_call_get_all_results(
        identity_client.list_availability_domains,
        compartment_id
    )
    # For demonstration, we just return the first availability domain but for Production code you should
    # have a better way of determining what is needed
    availability_domain = list_availability_domains_response.data[0]

    print()
    #print('Running in Availability Domain: {}'.format(availability_domain.name))

    return availability_domain


def get_shape(compute_client, compartment_id, availability_domain):
    list_shapes_response = oci.pagination.list_call_get_all_results(
        compute_client.list_shapes,
        compartment_id,
        availability_domain=availability_domain.name
    )
    shapes = list_shapes_response.data
    if len(shapes) == 0:
        raise RuntimeError('No available shape was found.')

    vm_shapes = list(filter(lambda shape: shape.shape.startswith("VM"), shapes))
    if len(vm_shapes) == 0:
        raise RuntimeError('No available VM shape was found.')
    
    for shape in vm_shapes:
        #print(shape.shape)
        if shape.shape==SHAPE:
            #print("找到:",shape.shape)
            return shape


def get_image(compute, compartment_id, shape):
    # Listing images is a paginated call, so we can use the oci.pagination module to get all results
    # without having to manually handle page tokens
    #
    # In this case, we want to find the image for the operating system we want to run, and which can
    # be used for the shape of instance we want to launch
    list_images_response = oci.pagination.list_call_get_all_results(
        compute.list_images,
        compartment_id,
        operating_system=OPERATING_SYSTEM,
        operating_system_version=OPERATING_SYSTEM_VERSION,
        shape=shape.shape
    )
    images = list_images_response.data
    if len(images) == 0:
        raise RuntimeError('No available image was found.')

    # For demonstration, we just return the first image but for Production code you should have a better
    # way of determining what is needed
    for image in images:
        pass
        #print(image)
    image = images[0]

    print('Found Image: {}'.format(image.id))
    print()

    return image


def get_launch_instance_details(compartment_id, availability_domain, shape, image, subnet, ssh_public_key):

    # We can use instance metadata to specify the SSH keys to be included in the
    # ~/.ssh/authorized_keys file for the default user on the instance via the special "ssh_authorized_keys" key.
    #
    # We can also provide arbitrary string keys and string values. If you are providing these, you should consider
    # whether defined and freeform tags on an instance would better meet your use case. See:
    # https://docs.cloud.oracle.com/Content/Identity/Concepts/taggingoverview.htm for more information
    # on tagging
    instance_metadata = {
        'ssh_authorized_keys': ssh_public_key,
        'some_metadata_item': 'some_item_value'
    }

    instance_name = INSTANCE_NAME
    instance_source_via_image_details = oci.core.models.InstanceSourceViaImageDetails(
        image_id=image.id
    )
    create_vnic_details = oci.core.models.CreateVnicDetails(
        subnet_id=SUBNET_ID,
        assign_private_dns_record = True,
		assign_public_ip = True
    )
    launch_instance_details = oci.core.models.LaunchInstanceDetails(
        display_name=instance_name,
        compartment_id=compartment_id,
        availability_domain=availability_domain.name,
        shape=shape.shape,
        metadata=instance_metadata,
        #extended_metadata=instance_extended_metadata,
        source_details=instance_source_via_image_details,
        create_vnic_details=create_vnic_details
    )
    return launch_instance_details


def launch_instance(compute_client_composite_operations, launch_instance_details):
    launch_instance_response = compute_client_composite_operations.launch_instance_and_wait_for_state(
        launch_instance_details,
        wait_for_states=[oci.core.models.Instance.LIFECYCLE_STATE_RUNNING]
    )
    instance = launch_instance_response.data

    print('Launched Instance: {}'.format(instance.id))
    print('{}'.format(instance))
    print()

    return instance




def print_instance_details(compute_client, virtual_network_client, instance):
    # We can find the private and public IP address of the instance by getting information on its VNIC(s). This
    # relationship is indirect, via the VnicAttachments of an instance

    # Note that listing VNIC attachments is a paginated operation so we can use the oci.pagination module to avoid
    # having to manually deal with page tokens.
    #
    # Since we're only interested in our specific instance, we can pass that as a filter to the list operation
    list_vnic_attachments_response = oci.pagination.list_call_get_all_results(
        compute_client.list_vnic_attachments,
        compartment_id,
        instance_id=instance.id
    )
    vnic_attachments = list_vnic_attachments_response.data

    vnic_attachment = vnic_attachments[0]
    get_vnic_response = virtual_network_client.get_vnic(vnic_attachment.vnic_id)
    vnic = get_vnic_response.data

    print('Virtual Network Interface Card')
    print('==============================')
    print('{}'.format(vnic))
    print()


if __name__ == "__main__":

    # Default config file and profile
    config = oci.config.from_file('~/.oci/config')
    print('read config')
    identity_client = oci.identity.IdentityClient(config)
    compute_client = oci.core.ComputeClient(config)
    print('compute_client',compute_client)
    compute_client_composite_operations = oci.core.ComputeClientCompositeOperations(compute_client)
    virtual_network_client = oci.core.VirtualNetworkClient(config)
    print('virtual_network_client',virtual_network_client)
    virtual_network_composite_operations = oci.core.VirtualNetworkClientCompositeOperations(virtual_network_client)

    availability_domain = get_availability_domain(identity_client, compartment_id)
    #print('availability_domain',availability_domain)
    shape = get_shape(compute_client, compartment_id, availability_domain)
    shape.ocpus=4
    shape.memory_in_gbs=24
    image = get_image(compute_client, compartment_id, shape)
    #print(image)
    
    launch_instance_details = get_launch_instance_details(
            compartment_id, availability_domain, shape, image, SUBNET_ID, ssh_public_key
        )
    launch_instance_details.shape_config={"memory_in_gbs": 24, "ocpus": 4}
    print(launch_instance_details)
    
    while True:
        try:
            instance = launch_instance(compute_client_composite_operations, launch_instance_details)
            print(instance)
            SendMsgByPushOver('create instance','ok',html=False,token_id=1)
            break
        except(oci.exceptions.RequestException):
            ret=sys.exc_info()
            print(time.strftime("错误：%a %b %d %H:%M:%S %Y", time.localtime()) ,ret)
            SendMsgByPushOver('OCI Connection aborted.','Connection reset by peer',html=False,token_id=1)
            
            identity_client = oci.identity.IdentityClient(config)
            compute_client = oci.core.ComputeClient(config)
            compute_client_composite_operations = oci.core.ComputeClientCompositeOperations(compute_client)
            virtual_network_client = oci.core.VirtualNetworkClient(config)
            virtual_network_composite_operations = oci.core.VirtualNetworkClientCompositeOperations(virtual_network_client)
            availability_domain = get_availability_domain(identity_client, compartment_id)
            shape = get_shape(compute_client, compartment_id, availability_domain)
            shape.ocpus=4
            shape.memory_in_gbs=24
            image = get_image(compute_client, compartment_id, shape)
            launch_instance_details = get_launch_instance_details(
                    compartment_id, availability_domain, shape, image, SUBNET_ID, ssh_public_key
                )
            launch_instance_details.shape_config={"memory_in_gbs": 24, "ocpus": 4}
            time.sleep(10)
            continue
        except(oci.exceptions.ServiceError):
            ret=sys.exc_info()[1]
            print(time.strftime("info：%a %b %d %H:%M:%S %Y", time.localtime()) ,ret.status,ret.message)
            time.sleep(2)
            if ret.status==500:
                 pass
            elif ret.status==429:
                 pass
            else:
                print(time.strftime("%a %b %d %H:%M:%S %Y", time.localtime()) ,ret.status,ret.message)
                exit(-1)


 
