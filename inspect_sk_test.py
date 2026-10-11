import re
import json

def list_body_joints(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
    
    pattern = re.compile(r'createNode\s+joint(?:\s+-[a-zA-Z0-9_]+)*\s+-n\s+"([^"]+)"')
    joints = pattern.findall(text)
    
    # Filter main body joints (ignoring lip, tongue, eyelid)
    face_keywords = ['lip', 'tongue', 'eye', 'jaw', 'cheek', 'nose', 'brow']
    body_joints = [j for j in joints if not any(k in j.lower() for k in face_keywords)]
    
    print("BODY_JOINTS:" + json.dumps({
        'total_joints': len(joints),
        'body_joints_count': len(body_joints),
        'body_joints': body_joints
    }, indent=2))

if __name__ == '__main__':
    list_body_joints(r'C:\Users\zwj87\Desktop\sk_test.ma')
