# Codex Auto Fix Context

- Repository: Fatty911/crawl_cars
- Workflow: 懂车帝爬虫
- Run ID: 27927412647
- Conclusion: failure
- Event: workflow_dispatch
- Head SHA: 1d8dbd4c557bfdfd318b58d3a85469f74aa3e522

## Task
你正在 GitHub Actions 中作为 Codex 自修复代理运行。
请只在确认是仓库源码、工作流、校验脚本或文档问题时修改代码。
如果日志显示是临时网络、代理订阅不可用、站点短暂限流、GitHub runner 抖动、或者半月完成后的正常跳过，请不要修改文件。

## Repository Rules
- 直接在 main 上修复；禁止 force push。
- 不要启动长时间爬虫；只运行语法校验、workflow 静态校验或很短的 smoke test。
- 修改代码或 workflow 后必须同步 README.md、CHANGELOG.md、HISTORY.md；代理相关还要同步 DOCKER_DEPLOY.md。
- 允许修改的范围：.github/workflows/、custom_scripts/、爬虫脚本、auto_fix_workflow.py、README/CHANGELOG/HISTORY/AGENTS/部署文档。
- 修复目标是让爬虫 workflow 符合：上午 08:00-12:30，下午 13:00-22:00；长跑自动按 Action 6 小时硬限制和当前时间窗口取更早截止，并保留提交缓冲；每半月完成后跳过。

## Logs
```text
dongchedi-crawl	Set up job	﻿2026-06-22T03:20:41.8958236Z Current runner version: '2.335.1'
dongchedi-crawl	Set up job	2026-06-22T03:20:41.8996298Z ##[group]Runner Image Provisioner
dongchedi-crawl	Set up job	2026-06-22T03:20:41.8998144Z Hosted Compute Agent
dongchedi-crawl	Set up job	2026-06-22T03:20:41.8999373Z Version: 20260611.554
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9000541Z Commit: 5e0782fdc9014723d3be820dd114dd31555c2bd1
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9002034Z Build Date: 2026-06-11T21:40:46Z
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9003201Z Worker ID: {ec22d3c7-0732-4790-bc76-a163a8ec4580}
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9004860Z Azure Region: eastus
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9005922Z ##[endgroup]
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9008900Z ##[group]Operating System
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9010057Z Ubuntu
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9011220Z 24.04.4
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9012147Z LTS
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9013142Z ##[endgroup]
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9014190Z ##[group]Runner Image
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9015485Z Image: ubuntu-24.04
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9016548Z Version: 20260615.205.1
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9018752Z Included Software: https://github.com/actions/runner-images/blob/ubuntu24/20260615.205/images/ubuntu/Ubuntu2404-Readme.md
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9022023Z Image Release: https://github.com/actions/runner-images/releases/tag/ubuntu24%2F20260615.205
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9023844Z ##[endgroup]
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9025920Z ##[group]GITHUB_TOKEN Permissions
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9029162Z Contents: write
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9030328Z Metadata: read
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9031426Z ##[endgroup]
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9034817Z Secret source: Actions
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9036160Z Prepare workflow directory
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9628202Z Prepare all required actions
dongchedi-crawl	Set up job	2026-06-22T03:20:41.9687226Z Getting action download info
dongchedi-crawl	Set up job	2026-06-22T03:20:42.2826859Z Download action repository 'actions/checkout@main' (SHA:9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0)
dongchedi-crawl	Set up job	2026-06-22T03:20:42.4450166Z Download action repository 'actions/cache@main' (SHA:27d5ce7f107fe9357f9df03efb73ab90386fccae)
dongchedi-crawl	Set up job	2026-06-22T03:20:42.5534689Z Download action repository 'actions/setup-python@main' (SHA:0cb1a84326b90186fcd211036c65b42819794c87)
dongchedi-crawl	Set up job	2026-06-22T03:20:42.7005705Z Download action repository 'browser-actions/setup-chrome@v2' (SHA:2e1d749697dd1612b833dba4a722266286fbefcd)
dongchedi-crawl	Set up job	2026-06-22T03:20:42.7962331Z Download action repository 'nanasess/setup-chromedriver@v2' (SHA:ef5c64a93512d266b23b80bae95e46a67f30e703)
dongchedi-crawl	Set up job	2026-06-22T03:20:42.9102925Z Download action repository 'actions/upload-artifact@v4' (SHA:ea165f8d65b6e75b540449e92b4886f43607fa02)
dongchedi-crawl	Set up job	2026-06-22T03:20:43.1849353Z Complete job name: dongchedi-crawl
dongchedi-crawl	Run actions/checkout@main	﻿2026-06-22T03:20:43.3416064Z ##[group]Run actions/checkout@main
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3417654Z with:
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3429083Z   token: ***
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3430084Z   repository: Fatty911/crawl_cars
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3431242Z   ssh-strict: true
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3432203Z   ssh-user: git
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3433178Z   persist-credentials: true
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3434236Z   clean: true
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3435216Z   sparse-checkout-cone-mode: true
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3436348Z   fetch-depth: 1
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3437280Z   fetch-tags: false
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3438506Z   show-progress: true
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3439557Z   lfs: false
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3440470Z   submodules: false
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3441462Z   set-safe-directory: true
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3442571Z   allow-unsafe-pr-checkout: false
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3444045Z env:
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3444949Z   RUN_TIME: 10800
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3445909Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3446972Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3448267Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3449516Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3450755Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3451844Z   MAX_CARS: 0
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3452792Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3453880Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.3454949Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.4623654Z Syncing repository: Fatty911/crawl_cars
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.4626617Z ##[group]Getting Git version info
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.4628616Z Working directory is '/home/runner/work/crawl_cars/crawl_cars'
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.4631400Z [command]/usr/bin/git version
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5212845Z git version 2.54.0
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5243746Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5255460Z Temporarily overriding HOME='/home/runner/work/_temp/8268a8ad-4970-4343-baf1-75baedc9d208' before making global git config changes
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5260520Z Adding repository directory to the temporary git global config as a safe directory
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5264065Z [command]/usr/bin/git config --global --add safe.directory /home/runner/work/crawl_cars/crawl_cars
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5334179Z Deleting the contents of '/home/runner/work/crawl_cars/crawl_cars'
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5346097Z ##[group]Determining repository object format
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5349122Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5351876Z ##[group]Initializing the repository
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5354255Z [command]/usr/bin/git init /home/runner/work/crawl_cars/crawl_cars
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5765951Z hint: Using 'master' as the name for the initial branch. This default branch name
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5770648Z hint: will change to "main" in Git 3.0. To configure the initial branch name
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5774899Z hint: to use in all of your new repositories, which will suppress this warning,
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5778554Z hint: call:
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5780151Z hint:
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5781946Z hint: 	git config --global init.defaultBranch <name>
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5784211Z hint:
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5786368Z hint: Names commonly chosen instead of 'master' are 'main', 'trunk' and
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5789846Z hint: 'development'. The just-created branch can be renamed via this command:
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5792704Z hint:
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5793843Z hint: 	git branch -m <name>
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5794881Z hint:
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5796201Z hint: Disable this message with "git config set advice.defaultBranchName false"
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5798660Z Initialized empty Git repository in /home/runner/work/crawl_cars/crawl_cars/.git/
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.5803367Z [command]/usr/bin/git remote add origin https://github.com/Fatty911/crawl_cars
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.7738541Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.7741480Z ##[group]Disabling automatic garbage collection
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.7743847Z [command]/usr/bin/git config --local gc.auto 0
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.7778696Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.7781447Z ##[group]Setting up auth
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.7783353Z Removing SSH command configuration
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.7786083Z [command]/usr/bin/git config --local --name-only --get-regexp core\.sshCommand
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.7824540Z [command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'core\.sshCommand' && git config --local --unset-all 'core.sshCommand' || :"
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.8154933Z Removing HTTP extra header
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.8160288Z [command]/usr/bin/git config --local --name-only --get-regexp http\.https\:\/\/github\.com\/\.extraheader
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.8194509Z [command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'http\.https\:\/\/github\.com\/\.extraheader' && git config --local --unset-all 'http.https://github.com/.extraheader' || :"
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.8415744Z Removing includeIf entries pointing to credentials config files
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.8420602Z [command]/usr/bin/git config --local --name-only --get-regexp ^includeIf\.gitdir:
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.8453520Z [command]/usr/bin/git submodule foreach --recursive git config --local --show-origin --name-only --get-regexp remote.origin.url
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.8697381Z [command]/usr/bin/git config --file /home/runner/work/_temp/git-credentials-a1af303e-39b7-46e8-884b-338648624167.config http.https://github.com/.extraheader AUTHORIZATION: basic ***
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.8741037Z [command]/usr/bin/git config --local includeIf.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git.path /home/runner/work/_temp/git-credentials-a1af303e-39b7-46e8-884b-338648624167.config
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.8772782Z [command]/usr/bin/git config --local includeIf.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git/worktrees/*.path /home/runner/work/_temp/git-credentials-a1af303e-39b7-46e8-884b-338648624167.config
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.8808090Z [command]/usr/bin/git config --local includeIf.gitdir:/github/workspace/.git.path /github/runner_temp/git-credentials-a1af303e-39b7-46e8-884b-338648624167.config
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.8839326Z [command]/usr/bin/git config --local includeIf.gitdir:/github/workspace/.git/worktrees/*.path /github/runner_temp/git-credentials-a1af303e-39b7-46e8-884b-338648624167.config
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.8872616Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.8875233Z ##[group]Fetching the repository
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:43.8882804Z [command]/usr/bin/git -c protocol.version=2 fetch --no-tags --prune --no-recurse-submodules --depth=1 origin +1d8dbd4c557bfdfd318b58d3a85469f74aa3e522:refs/remotes/origin/main
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1232223Z From https://github.com/Fatty911/crawl_cars
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1235499Z  * [new ref]         1d8dbd4c557bfdfd318b58d3a85469f74aa3e522 -> origin/main
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1285530Z [command]/usr/bin/git branch --list --remote origin/main
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1319872Z   origin/main
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1333518Z [command]/usr/bin/git rev-parse refs/remotes/origin/main
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1361079Z 1d8dbd4c557bfdfd318b58d3a85469f74aa3e522
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1367053Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1369141Z ##[group]Determining the checkout info
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1371028Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1373270Z [command]/usr/bin/git sparse-checkout disable
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1420067Z [command]/usr/bin/git config --local --unset-all extensions.worktreeConfig
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1450831Z ##[group]Checking out the ref
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1454137Z [command]/usr/bin/git checkout --progress --force -B main refs/remotes/origin/main
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1580548Z Switched to a new branch 'main'
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1582613Z branch 'main' set up to track 'origin/main'.
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1591359Z ##[endgroup]
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1638442Z [command]/usr/bin/git log -1 --format=%H
dongchedi-crawl	Run actions/checkout@main	2026-06-22T03:20:44.1665487Z 1d8dbd4c557bfdfd318b58d3a85469f74aa3e522
dongchedi-crawl	Prepare crawl period	﻿2026-06-22T03:20:44.1919534Z ##[group]Run mkdir -p crawl_state
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1920777Z ^[[36;1mmkdir -p crawl_state^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1921865Z ^[[36;1mCN_DAY=$(TZ=Asia/Shanghai date +%d)^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1923096Z ^[[36;1mCN_MONTH=$(TZ=Asia/Shanghai date +%Y%m)^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1924337Z ^[[36;1mif [ $((10#$CN_DAY)) -le 15 ]; then^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1925487Z ^[[36;1m  CRAWL_PERIOD="${CN_MONTH}_H1"^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1926524Z ^[[36;1melse^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1927381Z ^[[36;1m  CRAWL_PERIOD="${CN_MONTH}_H2"^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1928612Z ^[[36;1mfi^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1929686Z ^[[36;1mDONE_MARKER="crawl_state/dongchedi_${CRAWL_PERIOD}.done"^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1931342Z ^[[36;1mCURRENT_PERIOD_FILE="crawl_state/dongchedi_current_period"^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1932960Z ^[[36;1mecho "WORKFLOW_START_EPOCH=$(date +%s)" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1934416Z ^[[36;1mecho "CRAWL_PERIOD=$CRAWL_PERIOD" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1935922Z ^[[36;1mecho "DONGCHEDI_DONE_MARKER=$DONE_MARKER" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1937488Z ^[[36;1mecho "crawl_period=$CRAWL_PERIOD" >> $GITHUB_OUTPUT^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1939065Z ^[[36;1m^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1939872Z ^[[36;1mFORCE_RESTART="false"^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1940928Z ^[[36;1mDEBUG_MODE="true"^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1941843Z ^[[36;1m^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1942689Z ^[[36;1mif [ "$FORCE_RESTART" = "true" ]; then^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1943819Z ^[[36;1m  rm -f "$DONE_MARKER"^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1944768Z ^[[36;1mfi^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1945521Z ^[[36;1m^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1946837Z ^[[36;1mif [ "$FORCE_RESTART" != "true" ] && [ "$DEBUG_MODE" != "true" ] && [ -f "$DONE_MARKER" ]; then^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1948851Z ^[[36;1m  echo "$CRAWL_PERIOD 已完成全量懂车帝爬取，本半月不再爬取"^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1950087Z ^[[36;1m  echo "SKIP_CRAWL=true" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1951283Z ^[[36;1m  echo "skip=true" >> $GITHUB_OUTPUT^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1952648Z ^[[36;1m  exit 0^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1953450Z ^[[36;1mfi^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1954400Z ^[[36;1mecho "INCREMENTAL_MODE=true" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1955532Z ^[[36;1m^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1957159Z ^[[36;1mif [ "$FORCE_RESTART" = "true" ] || [ ! -f "$CURRENT_PERIOD_FILE" ] || [ "$(cat "$CURRENT_PERIOD_FILE")" != "$CRAWL_PERIOD" ]; then^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1959636Z ^[[36;1m  echo "进入新的半月周期 $CRAWL_PERIOD，启用增量模式（保留已有HTML）"^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1960889Z ^[[36;1m  rm -f dcd_step2_done^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1961857Z ^[[36;1mfi^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1962804Z ^[[36;1mecho "$CRAWL_PERIOD" > "$CURRENT_PERIOD_FILE"^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1964079Z ^[[36;1mecho "SKIP_CRAWL=false" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.1965304Z ^[[36;1mecho "skip=false" >> $GITHUB_OUTPUT^[[0m
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.2139252Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.2140505Z env:
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.2141455Z   RUN_TIME: 10800
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.2142523Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.2143716Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.2144965Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.2146268Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.2147639Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.2149295Z   MAX_CARS: 0
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.2150339Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.2151408Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Prepare crawl period	2026-06-22T03:20:44.2152351Z ##[endgroup]
dongchedi-crawl	Configure crawl window	﻿2026-06-22T03:20:44.2461603Z ##[group]Run if [ "$DEBUG_MODE" = "true" ]; then
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2463002Z ^[[36;1mif [ "$DEBUG_MODE" = "true" ]; then^[[0m
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2464193Z ^[[36;1m  echo "调试模式：跳过时间窗口限制，每次最多爬30车系"^[[0m
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2465366Z ^[[36;1m  echo "MAX_CARS=30" >> "$GITHUB_ENV"^[[0m
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2466595Z ^[[36;1m  echo "DEBUG_LIMIT=30" >> "$GITHUB_ENV"^[[0m
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2468061Z ^[[36;1m  echo "skip=false" >> "$GITHUB_OUTPUT"^[[0m
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2469230Z ^[[36;1melse^[[0m
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2470290Z ^[[36;1m  python custom_scripts/crawl_budget.py configure^[[0m
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2471690Z ^[[36;1m  echo "MAX_CARS=0" >> "$GITHUB_ENV"^[[0m
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2472799Z ^[[36;1mfi^[[0m
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2508114Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2509163Z env:
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2509967Z   RUN_TIME: 10800
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2510843Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2511814Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2512794Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2513929Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2515047Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2516042Z   MAX_CARS: 0
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2516887Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2518218Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2519437Z   WORKFLOW_START_EPOCH: 1782098444
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2520499Z   CRAWL_PERIOD: 202606_H2
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2521678Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202606_H2.done
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2522999Z   INCREMENTAL_MODE: true
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2523942Z   SKIP_CRAWL: false
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2524851Z   PROFILE_INPUT: auto
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2525741Z   DEBUG_MODE: true
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2526606Z ##[endgroup]
dongchedi-crawl	Configure crawl window	2026-06-22T03:20:44.2594111Z 调试模式：跳过时间窗口限制，每次最多爬30车系
dongchedi-crawl	Calculate delay from trigger time	﻿2026-06-22T03:20:44.2674027Z ##[group]Run echo "外部触发已经在 08:30/13:30 左右执行，不再追加随机启动延迟"
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2675389Z ^[[36;1mecho "外部触发已经在 08:30/13:30 左右执行，不再追加随机启动延迟"^[[0m
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2676583Z ^[[36;1mecho "delay=0" >> "$GITHUB_OUTPUT"^[[0m
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2711590Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2712544Z env:
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2713309Z   RUN_TIME: 10800
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2714155Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2715086Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2716032Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2717049Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2718391Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2719369Z   MAX_CARS: 30
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2720187Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2721154Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2722378Z   WORKFLOW_START_EPOCH: 1782098444
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2723390Z   CRAWL_PERIOD: 202606_H2
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2724541Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202606_H2.done
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2725894Z   INCREMENTAL_MODE: true
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2726815Z   SKIP_CRAWL: false
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2727647Z   DEBUG_LIMIT: 30
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2728768Z ##[endgroup]
dongchedi-crawl	Calculate delay from trigger time	2026-06-22T03:20:44.2795459Z 外部触发已经在 08:30/13:30 左右执行，不再追加随机启动延迟
dongchedi-crawl	Random delay	﻿2026-06-22T03:20:44.2876270Z ##[group]Run DELAY="0"
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2877259Z ^[[36;1mDELAY="0"^[[0m
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2878447Z ^[[36;1mif [ "$DELAY" != "0" ] && [ -n "$DELAY" ]; then^[[0m
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2879917Z ^[[36;1m  echo "Waiting $DELAY seconds ($(($DELAY / 60)) minutes)..."^[[0m
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2881256Z ^[[36;1m  sleep $DELAY^[[0m
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2882146Z ^[[36;1melse^[[0m
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2882961Z ^[[36;1m  echo "跳过延迟"^[[0m
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2883835Z ^[[36;1mfi^[[0m
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2919479Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2920464Z env:
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2921217Z   RUN_TIME: 10800
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2922073Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2923019Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2923968Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2924984Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2926073Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2927040Z   MAX_CARS: 30
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2928042Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2929078Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2930064Z   WORKFLOW_START_EPOCH: 1782098444
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2931073Z   CRAWL_PERIOD: 202606_H2
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2932221Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202606_H2.done
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2933515Z   INCREMENTAL_MODE: true
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2934435Z   SKIP_CRAWL: false
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2935267Z   DEBUG_LIMIT: 30
dongchedi-crawl	Random delay	2026-06-22T03:20:44.2936086Z ##[endgroup]
dongchedi-crawl	Random delay	2026-06-22T03:20:44.3003971Z 跳过延迟
dongchedi-crawl	Restore Dongchedi HTML cache	﻿2026-06-22T03:20:44.3203254Z ##[group]Run actions/cache@main
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3204553Z with:
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3205339Z   path: dongchedi/json
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3206289Z   key: dongchedi-html-202606_H2-27927412647-1
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3207459Z   restore-keys: dongchedi-html-202606_H2-
dongchedi-crawl	Restore Dongchedi HTML cache	
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3208886Z   enableCrossOsArchive: false
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3209884Z   fail-on-cache-miss: false
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3210808Z   lookup-only: false
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3211666Z   save-always: false
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3212501Z env:
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3213232Z   RUN_TIME: 10800
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3214080Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3215002Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3215946Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3216955Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3218229Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3219196Z   MAX_CARS: 30
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3220023Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3220974Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3222081Z   WORKFLOW_START_EPOCH: 1782098444
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3223077Z   CRAWL_PERIOD: 202606_H2
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3224218Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202606_H2.done
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3225479Z   INCREMENTAL_MODE: true
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3226376Z   SKIP_CRAWL: false
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3227200Z   DEBUG_LIMIT: 30
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.3228215Z ##[endgroup]
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:44.5266813Z Cache hit for restore-key: dongchedi-html-202606_H2-27894756982-1
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:45.4999176Z Received 141667163 of 141667163 (100.0%), 148.3 MBs/sec
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:45.5000155Z Cache Size: ~135 MB (141667163 B)
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:45.5032242Z [command]/usr/bin/tar -xf /home/runner/work/_temp/552e4a3d-1d45-458a-8fda-ed711026b2b9/cache.tzst -P -C /home/runner/work/crawl_cars/crawl_cars --use-compress-program unzstd
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:49.8789918Z Cache restored successfully
dongchedi-crawl	Restore Dongchedi HTML cache	2026-06-22T03:20:49.8939831Z Cache restored from key: dongchedi-html-202606_H2-27894756982-1
dongchedi-crawl	Report Dongchedi HTML cache	﻿2026-06-22T03:20:50.0266075Z ##[group]Run mkdir -p dongchedi/json
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0266942Z ^[[36;1mmkdir -p dongchedi/json^[[0m
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0267384Z ^[[36;1mHTML_COUNT=$(find dongchedi/json -type f -name '*.html' | wc -l)^[[0m
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0268238Z ^[[36;1mecho "Dongchedi HTML cache files: $HTML_COUNT"^[[0m
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0300991Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0301304Z env:
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0301537Z   RUN_TIME: 10800
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0301784Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0302056Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0302320Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0302642Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0302967Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0303243Z   MAX_CARS: 30
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0303479Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0303746Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0304026Z   WORKFLOW_START_EPOCH: 1782098444
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0304306Z   CRAWL_PERIOD: 202606_H2
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0304708Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202606_H2.done
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0305077Z   INCREMENTAL_MODE: true
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0305333Z   SKIP_CRAWL: false
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0305566Z   DEBUG_LIMIT: 30
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.0305805Z ##[endgroup]
dongchedi-crawl	Report Dongchedi HTML cache	2026-06-22T03:20:50.1720759Z Dongchedi HTML cache files: 4690
dongchedi-crawl	Run actions/setup-python@main	﻿2026-06-22T03:20:50.2178072Z ##[group]Run actions/setup-python@main
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2178708Z with:
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2179107Z   python-version: 3.12
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2179506Z   check-latest: false
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2185433Z   token: ***
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2185713Z   update-environment: true
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2185993Z   allow-prereleases: false
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2186265Z   freethreaded: false
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2186505Z env:
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2186705Z   RUN_TIME: 10800
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2186932Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2187187Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2187445Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2187726Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2188385Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2188659Z   MAX_CARS: 30
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2188884Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2189146Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2189411Z   WORKFLOW_START_EPOCH: 1782098444
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2189688Z   CRAWL_PERIOD: 202606_H2
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2190054Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202606_H2.done
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2190415Z   INCREMENTAL_MODE: true
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2190672Z   SKIP_CRAWL: false
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2190900Z   DEBUG_LIMIT: 30
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.2191120Z ##[endgroup]
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.3623626Z ##[group]Installed versions
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.9353487Z Successfully set up CPython (3.12.13)
dongchedi-crawl	Run actions/setup-python@main	2026-06-22T03:20:50.9354647Z ##[endgroup]
dongchedi-crawl	Run browser-actions/setup-chrome@v2	﻿2026-06-22T03:20:50.9658521Z ##[group]Run browser-actions/setup-chrome@v2
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9659011Z with:
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9659302Z   chrome-version: stable
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9659657Z   install-dependencies: false
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9659960Z   install-chromedriver: false
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9660218Z   no-sudo: false
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9660440Z env:
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9660644Z   RUN_TIME: 10800
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9660877Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9661121Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9661375Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9661647Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9661941Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9662193Z   MAX_CARS: 30
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9662412Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9662669Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9662928Z   WORKFLOW_START_EPOCH: 1782098444
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9663200Z   CRAWL_PERIOD: 202606_H2
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9663535Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202606_H2.done
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9663998Z   INCREMENTAL_MODE: true
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9664239Z   SKIP_CRAWL: false
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9664464Z   DEBUG_LIMIT: 30
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9664990Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9665480Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9665933Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9666342Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9666737Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9667137Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:50.9667480Z ##[endgroup]
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:51.0926450Z Setup chrome stable
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:51.0936913Z Attempting to download chrome stable...
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:51.1942330Z Acquiring chrome stable from https://storage.googleapis.com/chrome-for-testing-public/150.0.7871.24/linux64/chrome-linux64.zip
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:52.0423707Z Installing chrome...
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:52.1228161Z [command]/usr/bin/unzip -o -q /home/runner/work/_temp/2057c989-6577-471e-858d-b9d0666ed72f
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:57.0655572Z Successfully Installed chrome to /opt/hostedtoolcache/setup-chrome/chrome/stable/x64
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:57.0664146Z [command]/opt/hostedtoolcache/setup-chrome/chrome/stable/x64/chrome --version
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:57.1483711Z Google Chrome for Testing 150.0.7871.24 
dongchedi-crawl	Run browser-actions/setup-chrome@v2	2026-06-22T03:20:57.1520211Z Successfully setup chrome 150.0.7871.24
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	﻿2026-06-22T03:20:57.1654326Z ##[group]Run nanasess/setup-chromedriver@v2
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1654695Z with:
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1654908Z env:
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1655105Z   RUN_TIME: 10800
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1655339Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1655635Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1655890Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1656161Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1656458Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1656719Z   MAX_CARS: 30
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1656938Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1657193Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1657460Z   WORKFLOW_START_EPOCH: 1782098444
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1657731Z   CRAWL_PERIOD: 202606_H2
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1658410Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202606_H2.done
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1658781Z   INCREMENTAL_MODE: true
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1659022Z   SKIP_CRAWL: false
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1659246Z   DEBUG_LIMIT: 30
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1659542Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1660028Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1660473Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1660875Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1661284Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1661702Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.1662042Z ##[endgroup]
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.2392948Z ##setup chromedriver
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.2413027Z [command]/home/runner/work/_actions/nanasess/setup-chromedriver/v2/lib/setup-chromedriver.sh  linux64 
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.3662835Z CHROME_VERSION=149
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.3955940Z VERSION=149.0.7827.114
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.3957157Z Downloading https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json...
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.6349244Z Falling back to latest version of ChromeDriver for linux64
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.6367858Z VERSION3=149.0.7827
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.8114492Z VERSION=149.0.7827.155
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.9807196Z Installing ChromeDriver 149.0.7827.155 for linux64
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:57.9819582Z Downloading https://storage.googleapis.com/chrome-for-testing-public/149.0.7827.155/linux64/chromedriver-linux64.zip...
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:58.3153539Z Installing chromedriver to /usr/local/bin
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:58.3266634Z Chrome version:
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:58.3529335Z Google Chrome 149.0.7827.114 
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:58.3554653Z Chromedriver version:
dongchedi-crawl	Run nanasess/setup-chromedriver@v2	2026-06-22T03:20:58.3594706Z ChromeDriver 149.0.7827.155 (07b52360cc15066f987c910ab34dfbcd4a8778d2-refs/branch-heads/7827@{#3246})
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	﻿2026-06-22T03:20:58.3717709Z ##[group]Run pip install requests beautifulsoup4 selenium lxml PyYAML
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3719325Z ^[[36;1mpip install requests beautifulsoup4 selenium lxml PyYAML^[[0m
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3756210Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3756501Z env:
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3756714Z   RUN_TIME: 10800
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3756946Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3757202Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3757463Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3757740Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3758394Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3758664Z   MAX_CARS: 30
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3758892Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3759164Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3759431Z   WORKFLOW_START_EPOCH: 1782098444
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3759708Z   CRAWL_PERIOD: 202606_H2
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3760055Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202606_H2.done
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3760420Z   INCREMENTAL_MODE: true
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3760715Z   SKIP_CRAWL: false
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3760944Z   DEBUG_LIMIT: 30
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3761241Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3761698Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3762137Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3762535Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3762928Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3763325Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:58.3763666Z ##[endgroup]
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.2027267Z Collecting requests
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.2599625Z   Downloading requests-2.34.2-py3-none-any.whl.metadata (4.8 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.2775527Z Collecting beautifulsoup4
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.2817413Z   Downloading beautifulsoup4-4.15.0-py3-none-any.whl.metadata (3.8 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.3129652Z Collecting selenium
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.3168830Z   Downloading selenium-4.45.0-py3-none-any.whl.metadata (7.4 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.5511685Z Collecting lxml
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.5553357Z   Downloading lxml-6.1.1-cp312-cp312-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl.metadata (3.5 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.5921812Z Collecting PyYAML
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.5966883Z   Downloading pyyaml-6.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (2.4 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.6888926Z Collecting charset_normalizer<4,>=2 (from requests)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.6965339Z   Downloading charset_normalizer-3.4.7-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (40 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.7190630Z Collecting idna<4,>=2.5 (from requests)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.7230258Z   Downloading idna-3.18-py3-none-any.whl.metadata (6.1 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.7443757Z Collecting urllib3<3,>=1.26 (from requests)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.7487037Z   Downloading urllib3-2.7.0-py3-none-any.whl.metadata (6.9 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.7670603Z Collecting certifi>=2023.5.7 (from requests)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.7712802Z   Downloading certifi-2026.6.17-py3-none-any.whl.metadata (2.5 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.7893322Z Collecting soupsieve>=1.6.1 (from beautifulsoup4)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.7940085Z   Downloading soupsieve-2.8.4-py3-none-any.whl.metadata (4.6 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.8122121Z Collecting typing-extensions>=4.0.0 (from beautifulsoup4)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.8162984Z   Downloading typing_extensions-4.15.0-py3-none-any.whl.metadata (3.3 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.8329457Z Collecting trio<1.0,>=0.31.0 (from selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.8366724Z   Downloading trio-0.33.0-py3-none-any.whl.metadata (8.5 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.8504428Z Collecting trio-websocket<1.0,>=0.12.2 (from selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.8542392Z   Downloading trio_websocket-0.12.2-py3-none-any.whl.metadata (5.1 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.8741766Z Collecting websocket-client<2.0,>=1.8.0 (from selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.8780130Z   Downloading websocket_client-1.9.0-py3-none-any.whl.metadata (8.3 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.8973955Z Collecting attrs>=23.2.0 (from trio<1.0,>=0.31.0->selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.9016921Z   Downloading attrs-26.1.0-py3-none-any.whl.metadata (8.8 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.9173953Z Collecting sortedcontainers (from trio<1.0,>=0.31.0->selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.9211309Z   Downloading sortedcontainers-2.4.0-py2.py3-none-any.whl.metadata (10 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.9336017Z Collecting outcome (from trio<1.0,>=0.31.0->selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.9377595Z   Downloading outcome-1.3.0.post0-py2.py3-none-any.whl.metadata (2.6 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.9485527Z Collecting sniffio>=1.3.0 (from trio<1.0,>=0.31.0->selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.9525090Z   Downloading sniffio-1.3.1-py3-none-any.whl.metadata (3.9 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.9693925Z Collecting wsproto>=0.14 (from trio-websocket<1.0,>=0.12.2->selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.9731823Z   Downloading wsproto-1.3.2-py3-none-any.whl.metadata (5.2 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.9860952Z Collecting pysocks!=1.5.7,<2.0,>=1.5.6 (from urllib3[socks]<3.0,>=2.6.3->selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:20:59.9901972Z   Downloading PySocks-1.7.1-py3-none-any.whl.metadata (13 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.0068489Z Collecting h11<1,>=0.16.0 (from wsproto>=0.14->trio-websocket<1.0,>=0.12.2->selenium)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.0109154Z   Downloading h11-0.16.0-py3-none-any.whl.metadata (8.3 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.0200177Z Downloading requests-2.34.2-py3-none-any.whl (73 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.0295093Z Downloading charset_normalizer-3.4.7-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (216 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.0389541Z Downloading idna-3.18-py3-none-any.whl (65 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.0449286Z Downloading urllib3-2.7.0-py3-none-any.whl (131 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.0509174Z Downloading beautifulsoup4-4.15.0-py3-none-any.whl (109 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.0688673Z Downloading selenium-4.45.0-py3-none-any.whl (9.5 MB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.1588459Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 9.5/9.5 MB 108.5 MB/s  0:00:00
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.1626438Z Downloading trio-0.33.0-py3-none-any.whl (510 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.1704386Z Downloading trio_websocket-0.12.2-py3-none-any.whl (21 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.1767540Z Downloading typing_extensions-4.15.0-py3-none-any.whl (44 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.1831803Z Downloading PySocks-1.7.1-py3-none-any.whl (16 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.1893739Z Downloading websocket_client-1.9.0-py3-none-any.whl (82 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.1955246Z Downloading lxml-6.1.1-cp312-cp312-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl (5.2 MB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.2174746Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 5.2/5.2 MB 260.9 MB/s  0:00:00
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.2215023Z Downloading pyyaml-6.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (807 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.2278627Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 807.9/807.9 kB 136.9 MB/s  0:00:00
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.2316533Z Downloading attrs-26.1.0-py3-none-any.whl (67 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.2376628Z Downloading certifi-2026.6.17-py3-none-any.whl (133 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.2446063Z Downloading outcome-1.3.0.post0-py2.py3-none-any.whl (10 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.2506167Z Downloading sniffio-1.3.1-py3-none-any.whl (10 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.2565552Z Downloading soupsieve-2.8.4-py3-none-any.whl (37 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.2626542Z Downloading wsproto-1.3.2-py3-none-any.whl (24 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.2684895Z Downloading h11-0.16.0-py3-none-any.whl (37 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.2741097Z Downloading sortedcontainers-2.4.0-py2.py3-none-any.whl (29 kB)
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:00.3556717Z Installing collected packages: sortedcontainers, websocket-client, urllib3, typing-extensions, soupsieve, sniffio, PyYAML, pysocks, lxml, idna, h11, charset_normalizer, certifi, attrs, wsproto, requests, outcome, beautifulsoup4, trio, trio-websocket, selenium
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:02.4636901Z 
dongchedi-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-06-22T03:21:02.4663203Z Successfully installed PyYAML-6.0.3 attrs-26.1.0 beautifulsoup4-4.15.0 certifi-2026.6.17 charset_normalizer-3.4.7 h11-0.16.0 idna-3.18 lxml-6.1.1 outcome-1.3.0.post0 pysocks-1.7.1 requests-2.34.2 selenium-4.45.0 sniffio-1.3.1 sortedcontainers-2.4.0 soupsieve-2.8.4 trio-0.33.0 trio-websocket-0.12.2 typing-extensions-4.15.0 urllib3-2.7.0 websocket-client-1.9.0 wsproto-1.3.2
dongchedi-crawl	Setup environment	﻿2026-06-22T03:21:02.5556120Z ##[group]Run echo "MINIMAX_API_KEY=***" >> $GITHUB_ENV
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5558105Z ^[[36;1mecho "MINIMAX_API_KEY=***" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5559259Z ^[[36;1mecho "ZEN_API_KEY=***" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5560610Z ^[[36;1mecho "XAI_API_KEY=***" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5561824Z ^[[36;1mecho "OPENROUTER_API_KEY=***" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5562768Z ^[[36;1mecho "ACTION_PAT=***" >> $GITHUB_ENV^[[0m
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5609530Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5610018Z env:
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5610463Z   RUN_TIME: 10800
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5610906Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5611352Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5611797Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5612287Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5612835Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5613302Z   MAX_CARS: 30
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5613694Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5614208Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5614676Z   WORKFLOW_START_EPOCH: 1782098444
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5615161Z   CRAWL_PERIOD: 202606_H2
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5615733Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202606_H2.done
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5616354Z   INCREMENTAL_MODE: true
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5616776Z   SKIP_CRAWL: false
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5617156Z   DEBUG_LIMIT: 30
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5617708Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5618831Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5619682Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5620446Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5621217Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5621991Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
dongchedi-crawl	Setup environment	2026-06-22T03:21:02.5622641Z ##[endgroup]
dongchedi-crawl	Setup proxy if configured	﻿2026-06-22T03:21:02.5717136Z ##[group]Run python custom_scripts/setup_proxy_runtime.py --github-env "$GITHUB_ENV"
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5718192Z ^[[36;1mpython custom_scripts/setup_proxy_runtime.py --github-env "$GITHUB_ENV"^[[0m
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5749734Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5750017Z env:
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5750223Z   RUN_TIME: 10800
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5750463Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5750720Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5750986Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5751265Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5751559Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5751837Z   MAX_CARS: 30
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5752080Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5752343Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5752604Z   WORKFLOW_START_EPOCH: 1782098444
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5752884Z   CRAWL_PERIOD: 202606_H2
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5753209Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202606_H2.done
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5753625Z   INCREMENTAL_MODE: true
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5753867Z   SKIP_CRAWL: false
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5754089Z   DEBUG_LIMIT: 30
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5754381Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5754833Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5755271Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5755677Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5756073Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5756704Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5757592Z   MINIMAX_API_KEY: ***
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5758467Z   ZEN_API_KEY: ***
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5758982Z   XAI_API_KEY: ***
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5759420Z   OPENROUTER_API_KEY: ***
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5759790Z   ACTION_PAT: ***
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5760646Z   PROXY_SUBSCRIPTIONS: ***
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:02.5760918Z ##[endgroup]
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0506114Z 解析订阅: https://69.63.197.45:6206/***
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0506694Z 获取订阅成功: https://69.63.197.45:6206/*** 状态码: 200 内容长度: 31413
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0507197Z 非Base64格式，直接返回，内容长度: 31413
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0507542Z 尝试解析链接格式，共 1 行
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0508226Z 解析完成，获取 0 个节点
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0508790Z 解析订阅: https://api2.riolu01.link/***
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0509529Z 获取订阅成功: https://api2.riolu01.link/*** 状态码: 200 内容长度: 409622
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0510130Z 非Base64格式，直接返回，内容长度: 409622
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0510668Z 检测到Clash YAML格式配置，尝试解析...
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0511030Z 从Clash配置解析到 54 个节点
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0511403Z 解析到 54 个代理节点，准备启动本地 mihomo
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0511756Z 配置已保存到: /tmp/mihomo/config.yaml
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0512136Z 下载 mihomo 最新 Linux amd64 运行文件...
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0512530Z mihomo 已准备: /tmp/mihomo-bin/mihomo
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0512935Z mihomo PID: 2439, 日志: /tmp/mihomo.log
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0513411Z 代理连通性测试通过: http://www.gstatic.com/generate_204 HTTP 204
dongchedi-crawl	Setup proxy if configured	2026-06-22T03:21:15.0513950Z 代理已启用：后续爬虫步骤将通过 http://127.0.0.1:7890 访问外网
dongchedi-crawl	Check if step2 already done	﻿2026-06-22T03:21:15.0872847Z ##[group]Run if [ -f "$DONGCHEDI_DONE_MARKER" ]; then
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0873653Z ^[[36;1mif [ -f "$DONGCHEDI_DONE_MARKER" ]; then^[[0m
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0874282Z ^[[36;1m  echo "done=true" >> $GITHUB_OUTPUT^[[0m
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0874808Z ^[[36;1melse^[[0m
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0875249Z ^[[36;1m  echo "done=false" >> $GITHUB_OUTPUT^[[0m
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0875787Z ^[[36;1mfi^[[0m
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0922435Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0922920Z env:
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0923292Z   RUN_TIME: 10800
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0923752Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0924204Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0924659Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0925143Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0925658Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0926109Z   MAX_CARS: 30
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0926494Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0926981Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0927441Z   WORKFLOW_START_EPOCH: 1782098444
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0928303Z   CRAWL_PERIOD: 202606_H2
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0928885Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202606_H2.done
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0929555Z   INCREMENTAL_MODE: true
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0930016Z   SKIP_CRAWL: false
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0930417Z   DEBUG_LIMIT: 30
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0930948Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0931767Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0932609Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0933363Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0934121Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0934892Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0936528Z   MINIMAX_API_KEY: ***
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0937302Z   ZEN_API_KEY: ***
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0939086Z   XAI_API_KEY: ***
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0939696Z   OPENROUTER_API_KEY: ***
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0940148Z   ACTION_PAT: ***
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0940433Z   PROXY_ENABLED: true
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0940749Z   PROXY_CONFIG_FILE: /tmp/proxies.json
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0941129Z   HTTP_PROXY: http://127.0.0.1:7890
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0941494Z   HTTPS_PROXY: http://127.0.0.1:7890
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0941854Z   ALL_PROXY: socks5://127.0.0.1:7891
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0942220Z   http_proxy: http://127.0.0.1:7890
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0942571Z   https_proxy: http://127.0.0.1:7890
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0943207Z   all_proxy: socks5://127.0.0.1:7891
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0943550Z   NO_PROXY: 127.0.0.1,localhost
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0943862Z   no_proxy: 127.0.0.1,localhost
dongchedi-crawl	Check if step2 already done	2026-06-22T03:21:15.0944172Z ##[endgroup]
dongchedi-crawl	Run step1 to get series list	﻿2026-06-22T03:21:15.1041184Z ##[group]Run set -o pipefail
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1041555Z ^[[36;1mset -o pipefail^[[0m
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1041844Z ^[[36;1mif [ "$PROXY_ENABLED" = "true" ]; then^[[0m
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1042209Z ^[[36;1m  echo "使用代理模式运行 step1 (mihomo round-robin)"^[[0m
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1042744Z ^[[36;1m  python crawl_dongchedi.py --step 1 --auto --time-limit "$RUN_TIME" 2>&1 | tee step1_error.log^[[0m
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1043227Z ^[[36;1melse^[[0m
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1043451Z ^[[36;1m  echo "无代理，直接运行 step1"^[[0m
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1043839Z ^[[36;1m  python crawl_dongchedi.py --step 1 --auto --time-limit "$RUN_TIME"^[[0m
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1044238Z ^[[36;1mfi^[[0m
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1044488Z ^[[36;1mif [ -f dongchedi/progress.json ]; then^[[0m
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1044949Z ^[[36;1m  git config --local user.email "github-actions[bot]@users.noreply.github.com"^[[0m
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1045460Z ^[[36;1m  git config --local user.name "github-actions[bot]"^[[0m
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1045809Z ^[[36;1m  git add -A^[[0m
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1046238Z ^[[36;1m  git diff --staged --quiet || git commit -m "Dongchedi step1 - series list - $(date +%H:%M)"^[[0m
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1050589Z ^[[36;1m  bash custom_scripts/git_sync_progress.sh "***github.com/Fatty911/crawl_cars.git"^[[0m
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1051065Z ^[[36;1mfi^[[0m
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1082924Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1083207Z env:
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1083422Z   RUN_TIME: 10800
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1083660Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1083920Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1084172Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1084451Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1084755Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1085018Z   MAX_CARS: 30
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1085288Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1085549Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1085805Z   WORKFLOW_START_EPOCH: 1782098444
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1086074Z   CRAWL_PERIOD: 202606_H2
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1086389Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202606_H2.done
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1086754Z   INCREMENTAL_MODE: true
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1086995Z   SKIP_CRAWL: false
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1087221Z   DEBUG_LIMIT: 30
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1087508Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1088333Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1088805Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1089222Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1089622Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1090024Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1090860Z   MINIMAX_API_KEY: ***
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1091279Z   ZEN_API_KEY: ***
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1091775Z   XAI_API_KEY: ***
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1092199Z   OPENROUTER_API_KEY: ***
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1092610Z   ACTION_PAT: ***
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1092859Z   PROXY_ENABLED: true
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1093151Z   PROXY_CONFIG_FILE: /tmp/proxies.json
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1093459Z   HTTP_PROXY: http://127.0.0.1:7890
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1093762Z   HTTPS_PROXY: http://127.0.0.1:7890
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1094076Z   ALL_PROXY: socks5://127.0.0.1:7891
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1094360Z   http_proxy: http://127.0.0.1:7890
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1094640Z   https_proxy: http://127.0.0.1:7890
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1094917Z   all_proxy: socks5://127.0.0.1:7891
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1095191Z   NO_PROXY: 127.0.0.1,localhost
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1095449Z   no_proxy: 127.0.0.1,localhost
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1095701Z ##[endgroup]
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1155937Z 使用代理模式运行 step1 (mihomo round-robin)
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1520896Z Traceback (most recent call last):
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1529388Z   File "/home/runner/work/crawl_cars/crawl_cars/crawl_dongchedi.py", line 17, in <module>
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1530061Z     from crawl_state.registry import ModelRegistry
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1530535Z ModuleNotFoundError: No module named 'crawl_state.registry'
dongchedi-crawl	Run step1 to get series list	2026-06-22T03:21:15.1583294Z ##[error]Process completed with exit code 1.
dongchedi-crawl	Disable proxy for GitHub artifact upload	﻿2026-06-22T03:21:15.1668253Z ##[group]Run {
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1668588Z ^[[36;1m{^[[0m
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1668820Z ^[[36;1m  echo "HTTP_PROXY="^[[0m
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1669097Z ^[[36;1m  echo "HTTPS_PROXY="^[[0m
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1669369Z ^[[36;1m  echo "ALL_PROXY="^[[0m
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1669622Z ^[[36;1m  echo "http_proxy="^[[0m
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1669969Z ^[[36;1m  echo "https_proxy="^[[0m
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1670247Z ^[[36;1m  echo "all_proxy="^[[0m
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1670500Z ^[[36;1m} >> "$GITHUB_ENV"^[[0m
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1701560Z shell: /usr/bin/bash -e {0}
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1702034Z env:
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1702368Z   RUN_TIME: 10800
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1702790Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1703234Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1703500Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1703773Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1704084Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1704346Z   MAX_CARS: 30
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1704568Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1704852Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1705131Z   WORKFLOW_START_EPOCH: 1782098444
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1705430Z   CRAWL_PERIOD: 202606_H2
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1705768Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202606_H2.done
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1706135Z   INCREMENTAL_MODE: true
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1706390Z   SKIP_CRAWL: false
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1706633Z   DEBUG_LIMIT: 30
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1706925Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1707525Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1708410Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1708944Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1709357Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1709759Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1710606Z   MINIMAX_API_KEY: ***
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1711048Z   ZEN_API_KEY: ***
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1711542Z   XAI_API_KEY: ***
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1711965Z   OPENROUTER_API_KEY: ***
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1712327Z   ACTION_PAT: ***
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1712566Z   PROXY_ENABLED: true
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1712821Z   PROXY_CONFIG_FILE: /tmp/proxies.json
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1713137Z   HTTP_PROXY: http://127.0.0.1:7890
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1713431Z   HTTPS_PROXY: http://127.0.0.1:7890
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1713721Z   ALL_PROXY: socks5://127.0.0.1:7891
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1714002Z   http_proxy: http://127.0.0.1:7890
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1714284Z   https_proxy: http://127.0.0.1:7890
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1714579Z   all_proxy: socks5://127.0.0.1:7891
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1714859Z   NO_PROXY: 127.0.0.1,localhost
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1715122Z   no_proxy: 127.0.0.1,localhost
dongchedi-crawl	Disable proxy for GitHub artifact upload	2026-06-22T03:21:15.1715372Z ##[endgroup]
dongchedi-crawl	Upload error log	﻿2026-06-22T03:21:15.1824708Z Node 20 is being deprecated. This workflow is running with Node 24 by default. If you need to temporarily use Node 20, you can set the ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true environment variable. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1826091Z ##[group]Run actions/upload-artifact@v4
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1826460Z with:
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1826673Z   name: error-log
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1826922Z   path: step1_error.log
dongchedi-crawl	Upload error log	step2_error.log
dongchedi-crawl	Upload error log	
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1827224Z   if-no-files-found: ignore
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1827472Z   retention-days: 7
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1827704Z   compression-level: 6
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1828309Z   overwrite: false
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1828824Z   include-hidden-files: false
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1829082Z env:
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1829284Z   RUN_TIME: 10800
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1829515Z   MORNING_RUN_TIME: 10800
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1829772Z   AFTERNOON_RUN_TIME: 21000
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1830050Z   MAX_WORKFLOW_SECONDS: 21600
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1830326Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1830618Z   WINDOW_END_BUFFER_SECONDS: 900
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1830876Z   MAX_CARS: 30
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1831088Z   CRAWL_MIN_DELAY_SECONDS: 3
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1831344Z   CRAWL_MAX_DELAY_SECONDS: 8
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1831601Z   WORKFLOW_START_EPOCH: 1782098444
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1831873Z   CRAWL_PERIOD: 202606_H2
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1832180Z   DONGCHEDI_DONE_MARKER: crawl_state/dongchedi_202606_H2.done
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1832669Z   INCREMENTAL_MODE: true
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1833059Z   SKIP_CRAWL: false
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1833350Z   DEBUG_LIMIT: 30
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1833833Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1834538Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1835368Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1836148Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1836757Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1837167Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1838248Z   MINIMAX_API_KEY: ***
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1838704Z   ZEN_API_KEY: ***
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1839204Z   XAI_API_KEY: ***
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1839630Z   OPENROUTER_API_KEY: ***
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1839997Z   ACTION_PAT: ***
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1840242Z   PROXY_ENABLED: true
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1840507Z   PROXY_CONFIG_FILE: /tmp/proxies.json
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1840792Z   HTTP_PROXY: 
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1841011Z   HTTPS_PROXY: 
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1841225Z   ALL_PROXY: 
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1841433Z   http_proxy: 
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1841644Z   https_proxy: 
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1841856Z   all_proxy: 
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1842072Z   NO_PROXY: 127.0.0.1,localhost
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1842332Z   no_proxy: 127.0.0.1,localhost
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.1842573Z ##[endgroup]
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.3548876Z (node:2454) [DEP0040] DeprecationWarning: The `punycode` module is deprecated. Please use a userland alternative instead.
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.3549817Z (Use `node --trace-deprecation ...` to show where the warning was created)
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.3634734Z Multiple search paths detected. Calculating the least common ancestor of all paths
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.3659172Z The least common ancestor is /home/runner/work/crawl_cars/crawl_cars. This will be the root directory of the artifact
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.3688939Z With the provided path, there will be 1 file uploaded
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.3718899Z Artifact name is valid!
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.3738902Z Root directory input is valid!
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.5647857Z Beginning upload of artifact content to blob storage
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.5844330Z (node:2454) [DEP0169] DeprecationWarning: `url.parse()` behavior is not standardized and prone to errors that have security implications. Use the WHATWG URL API instead. CVEs are not issued for `url.parse()` vulnerabilities.
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.6277714Z Uploaded bytes 304
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.6470534Z Finished uploading artifact content to blob storage!
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.6471634Z SHA256 digest of uploaded artifact zip is 935ddc8d2d59491634af54c3078413ec1cde98d947a37fb37c85df74c609022b
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.6472836Z Finalizing artifact upload
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.8310965Z Artifact error-log.zip successfully finalized. Artifact ID 7782541583
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.8312304Z Artifact error-log has been successfully uploaded! Final size is 304 bytes. Artifact ID is 7782541583
dongchedi-crawl	Upload error log	2026-06-22T03:21:15.8319259Z Artifact download URL: https://github.com/Fatty911/crawl_cars/actions/runs/27927412647/artifacts/7782541583
dongchedi-crawl	Post Run actions/checkout@main	﻿2026-06-22T03:21:15.8544539Z Post job cleanup.
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:15.9423569Z [command]/usr/bin/git version
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:15.9464235Z git version 2.54.0
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:15.9502861Z Temporarily overriding HOME='/home/runner/work/_temp/9ac0ff8c-33c4-42ef-8a53-3250b60c4275' before making global git config changes
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:15.9503883Z Adding repository directory to the temporary git global config as a safe directory
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:15.9518752Z [command]/usr/bin/git config --global --add safe.directory /home/runner/work/crawl_cars/crawl_cars
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:15.9554038Z Removing SSH command configuration
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:15.9561208Z [command]/usr/bin/git config --local --name-only --get-regexp core\.sshCommand
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:15.9603553Z [command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'core\.sshCommand' && git config --local --unset-all 'core.sshCommand' || :"
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:15.9839452Z Removing HTTP extra header
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:15.9844909Z [command]/usr/bin/git config --local --name-only --get-regexp http\.https\:\/\/github\.com\/\.extraheader
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:15.9885534Z [command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'http\.https\:\/\/github\.com\/\.extraheader' && git config --local --unset-all 'http.https://github.com/.extraheader' || :"
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0118680Z Removing includeIf entries pointing to credentials config files
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0126122Z [command]/usr/bin/git config --local --name-only --get-regexp ^includeIf\.gitdir:
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0188995Z includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git.path
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0190100Z includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git/worktrees/*.path
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0191018Z includeif.gitdir:/github/workspace/.git.path
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0191751Z includeif.gitdir:/github/workspace/.git/worktrees/*.path
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0200482Z [command]/usr/bin/git config --local --get-all includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git.path
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0225050Z /home/runner/work/_temp/git-credentials-a1af303e-39b7-46e8-884b-338648624167.config
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0236538Z [command]/usr/bin/git config --local --unset includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git.path /home/runner/work/_temp/git-credentials-a1af303e-39b7-46e8-884b-338648624167.config
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0274257Z [command]/usr/bin/git config --local --get-all includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git/worktrees/*.path
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0309000Z /home/runner/work/_temp/git-credentials-a1af303e-39b7-46e8-884b-338648624167.config
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0322069Z [command]/usr/bin/git config --local --unset includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git/worktrees/*.path /home/runner/work/_temp/git-credentials-a1af303e-39b7-46e8-884b-338648624167.config
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0358770Z [command]/usr/bin/git config --local --get-all includeif.gitdir:/github/workspace/.git.path
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0382145Z /github/runner_temp/git-credentials-a1af303e-39b7-46e8-884b-338648624167.config
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0391886Z [command]/usr/bin/git config --local --unset includeif.gitdir:/github/workspace/.git.path /github/runner_temp/git-credentials-a1af303e-39b7-46e8-884b-338648624167.config
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0426942Z [command]/usr/bin/git config --local --get-all includeif.gitdir:/github/workspace/.git/worktrees/*.path
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0451629Z /github/runner_temp/git-credentials-a1af303e-39b7-46e8-884b-338648624167.config
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0463034Z [command]/usr/bin/git config --local --unset includeif.gitdir:/github/workspace/.git/worktrees/*.path /github/runner_temp/git-credentials-a1af303e-39b7-46e8-884b-338648624167.config
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0499158Z [command]/usr/bin/git submodule foreach --recursive git config --local --show-origin --name-only --get-regexp remote.origin.url
dongchedi-crawl	Post Run actions/checkout@main	2026-06-22T03:21:16.0756436Z Removing credentials config '/home/runner/work/_temp/git-credentials-a1af303e-39b7-46e8-884b-338648624167.config'
dongchedi-crawl	Complete job	﻿2026-06-22T03:21:16.0916249Z Cleaning up orphan processes
dongchedi-crawl	Complete job	2026-06-22T03:21:16.1268156Z Terminate orphan process: pid (2439) (mihomo)
dongchedi-crawl	Complete job	2026-06-22T03:21:16.1279130Z ##[warning]Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24: actions/upload-artifact@v4. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/

```
