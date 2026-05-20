import re, sys
sys.stdout.reconfigure(encoding='utf-8')

c = open('src/styles.css', encoding='utf-8').read()
print('Total size:', len(c))

for pattern in ['edit-profile-overlay', 'edit-profile-modal', 'user-menu-wrap', 'User Menu']:
    positions = [m.start() for m in re.finditer(re.escape(pattern), c)]
    print(f'{pattern}: {positions}')

# Show what's at position 42500 onwards
print('\n--- From pos 42500 ---')
print(c[42500:42650].replace('\n', '|'))
