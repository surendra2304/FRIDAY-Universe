import oci

config = oci.config.from_file("C:/Users/Surendra/.oci/config")
compute = oci.core.ComputeClient(config)
block = oci.core.BlockstorageClient(config)

compartment_id = config["tenancy"]
instances = compute.list_instances(compartment_id).data

for inst in instances:
    print(f"Instance: {inst.display_name} | Shape: {inst.shape} | State: {inst.lifecycle_state} | ID: {inst.id}")
    if inst.lifecycle_state == "RUNNING":
        bva = compute.list_boot_volume_attachments(inst.availability_domain, compartment_id, instance_id=inst.id).data
        for a in bva:
            bv = block.get_boot_volume(a.boot_volume_id).data
            print(f"  Boot Volume: {bv.display_name} | Size: {bv.size_in_gbs} GB | State: {bv.lifecycle_state} | ID: {bv.id}")
