# Simple utilite for auto-coommit and auto-push repositories

# Install
1. Clone this repository
2. Execute 
```bash
./install.sh
```
3. Do't remove cloned repository

# Useful to know
## Track and untrack repository
List of repositories store in ~/.config/git-auto-commit/repos.list
### Add repository
```bash
git manager path_to_your_repositiry
```
### Untrack repository
```bash
git manager -d path_to_your_repositiry
```
## Change backup timer
Edit this file ~/.config/systemd/user/git-auto-commit.service

# Details
- For install need root
- Using systemd timer (not cron)
