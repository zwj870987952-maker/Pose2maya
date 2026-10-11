import maya.cmds as cmds
import json

def cleanup_standalone_template():
    # Delete non-sk_test standalone joints that were created earlier without namespace
    to_delete = []
    for j in cmds.ls(assemblies=True):
        if j.startswith("mhr_") or j in ["root", "c_spine0", "c_spine1", "c_spine2", "c_spine3", "c_neck", "c_head", 
                                        "r_clavicle", "r_uparm", "r_lowarm", "r_wrist", "r_wrist_twist",
                                        "l_clavicle", "l_uparm", "l_lowarm", "l_wrist", "l_wrist_twist",
                                        "r_upleg", "r_lowleg", "r_foot", "r_talocrural", "r_subtalar", "r_transversetarsal", "r_ball",
                                        "l_upleg", "l_lowleg", "l_foot", "l_talocrural", "l_subtalar", "l_transversetarsal", "l_ball"]:
            to_delete.append(j)
    if to_delete:
        cmds.delete(to_delete)
        print("CLEANUP_DONE:" + json.dumps({'deleted': to_delete}))
    else:
        print("CLEANUP_DONE: none")

if __name__ == '__main__':
    cleanup_standalone_template()
