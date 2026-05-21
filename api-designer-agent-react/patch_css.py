import os

path = 'src/styles.css'
content = open(path, encoding='utf-8').read()

print('File size:', len(content))
print('Has max-height 90vh:', 'max-height: 90vh' in content)

content2 = content.replace('max-height: 90vh', 'height: 480px', 1)
print('Changed:', content != content2)

with open(path, 'w', encoding='utf-8', newline='') as f:
    f.write(content2)

content3 = open(path, encoding='utf-8').read()
print('Verify height 480px:', 'height: 480px' in content3)
print('Verify max-height gone:', 'max-height: 90vh' not in content3)
print('New file size:', os.path.getsize(path))
