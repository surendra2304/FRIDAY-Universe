import time
import oci

config = oci.config.from_file("C:/Users/Surendra/.oci/config")
block = oci.core.BlockstorageClient(config)

boot_volume_id = "ocid1.bootvolume.oc1.ap-hyderabad-1.abuhsljrmts4exjjsfswjpmfyfblxow5tydfqz2jevvi6lplyecphivoponq"
target_size_gb = 100

print(f"Fetching current boot volume details for {boot_volume_id}...")
bv = block.get_boot_volume(boot_volume_id).data
print(f"Current Size: {bv.size_in_gbs} GB | Lifecycle: {bv.lifecycle_state}")

if bv.size_in_gbs >= target_size_gb:
    print(f"Volume is already {bv.size_in_gbs} GB (>= {target_size_gb} GB). No OCI resize needed.")
else:
    print(f"Requesting resize from {bv.size_in_gbs} GB -> {target_size_gb} GB...")
    update_details = oci.core.models.UpdateBootVolumeDetails(size_in_gbs=target_size_gb)
    res = block.update_boot_volume(boot_volume_id, update_details).data
    print(f"Update initiated. New state: {res.lifecycle_state} | Target size: {res.size_in_gbs} GB")

    print("Waiting for volume to become AVAILABLE...")
    while True:
        bv = block.get_boot_volume(boot_volume_id).data
        print(f"  Status: {bv.lifecycle_state} (Size: {bv.size_in_gbs} GB)")
        if bv.lifecycle_state == "AVAILABLE" and bv.size_in_gbs == target_size_gb:
            print("OCI Boot Volume resize successfully completed!")
            break
        time.sleep(5)
