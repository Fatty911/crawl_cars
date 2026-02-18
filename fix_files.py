"""Fix remaining tab/space issues in test_autohome.py download_car_pages()."""
import re
import os

DIR = os.path.dirname(os.path.abspath(__file__))


def fix_autohome():
    path = os.path.join(DIR, 'test_autohome.py')
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()

    # Normalize all tabs to 4 spaces
    src = src.expandtabs(4)

    # Remove car_id filter comment if still present
    src = re.sub(r'if car_id: #and.*', 'if car_id:', src)

    # Fix the26-space indented block inside if car_id to 28spaces
    lines = src.split('\n')
    fixed = []
    in_block = False
    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if stripped.startswith('if car_id:') and indent == 24:
            in_block = True
            fixed.append(line)
            continue
        if in_block:
            if stripped == '':
                fixed.append('')
                continue
            if indent == 26:
                fixed.append(' ' * 28 + stripped)
            else:
                fixed.append(line)
            if 'f.write(content)' in stripped:
                in_block = False
            continue
        fixed.append(line)
    src = '\n'.join(fixed)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(src)
    print(f'Fixed: {path}')


if __name__ == '__main__':
    fix_autohome()
    print('Done!')
