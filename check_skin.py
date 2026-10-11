import maya.cmds as cmds
import json

def check_skin():
    skin_clusters = cmds.ls(type='skinCluster') or []
    print("SKIN_INFO:" + json.dumps({
        'skin_clusters': skin_clusters,
        'count': len(skin_clusters)
    }))

if __name__ == '__main__':
    check_skin()
