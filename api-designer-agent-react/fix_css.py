import re, sys
sys.stdout.reconfigure(encoding='utf-8')

path = 'src/styles.css'
c = open(path, encoding='utf-8').read()

# 1. Fix edit-profile-modal: replace max-height: 90vh with height: 480px
#    The block starts at the known position
modal_start = c.find('.edit-profile-modal {')
print('edit-profile-modal at:', modal_start)

# Find the closing brace by counting braces
depth = 0
end = modal_start
for i in range(modal_start, len(c)):
    if c[i] == '{': depth += 1
    elif c[i] == '}':
        depth -= 1
        if depth == 0:
            end = i
            break

block = c[modal_start:end+1]
print('Original block:', block.replace('\n','|'))

new_block = block.replace('  max-height: 90vh;\n', '  height: 480px;\n')
print('New block:', new_block.replace('\n','|'))
print('Changed:', block != new_block)

# 2. Revert accidental height: 480px in preview-modal
#    Find preview-modal block and restore max-height: 100%
preview_start = c.find('.preview-modal {')
print('\npreview-modal at:', preview_start)
depth2 = 0
end2 = preview_start
for i in range(preview_start, len(c)):
    if c[i] == '{': depth2 += 1
    elif c[i] == '}':
        depth2 -= 1
        if depth2 == 0:
            end2 = i
            break

pblock = c[preview_start:end2+1]
print('Preview block:', pblock.replace('\n','|'))

new_pblock = pblock.replace('  height: 480px;\n', '  max-height: 100%;\n')
print('Preview new block:', new_pblock.replace('\n','|'))
print('Preview changed:', pblock != new_pblock)

# Apply both changes
result = c[:modal_start] + new_block + c[end+1:]
# Now fix preview-modal in the result
result = result.replace(pblock, new_pblock, 1)

open(path, 'w', encoding='utf-8', newline='').write(result)
print('\nWritten. Verifying...')

c2 = open(path, encoding='utf-8').read()
modal_start2 = c2.find('.edit-profile-modal {')
depth3 = 0
end3 = modal_start2
for i in range(modal_start2, len(c2)):
    if c2[i] == '{': depth3 += 1
    elif c2[i] == '}':
        depth3 -= 1
        if depth3 == 0:
            end3 = i
            break
print('Final edit-profile-modal block:', c2[modal_start2:end3+1].replace('\n','|'))
