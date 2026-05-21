import re, sys
sys.stdout.reconfigure(encoding='utf-8')

c = open('src/styles.css', encoding='utf-8').read()
print('Total file size:', len(c))

print('\n--- edit-profile-modal occurrences ---')
for m in re.finditer(r'edit-profile-modal', c):
    snippet = c[m.start():m.start()+80].replace('\n','|')
    print('pos:', m.start(), snippet)

print('\n--- max-height occurrences ---')
for m in re.finditer(r'max-height', c):
    snippet = c[m.start()-60:m.start()+30].replace('\n','|')
    print('pos:', m.start(), snippet)

print('\n--- height: 480 occurrences ---')
for m in re.finditer(r'height: 480', c):
    snippet = c[m.start()-60:m.start()+30].replace('\n','|')
    print('pos:', m.start(), snippet)
