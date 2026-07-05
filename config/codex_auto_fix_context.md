# Codex Auto Fix Context

- Repository: Fatty911/crawl_cars
- Workflow: 汽车之家爬虫
- Run ID: 28749081086
- Conclusion: failure
- Event: workflow_dispatch
- Head SHA: 18240c947ec83967373af73280d3c10748762bd8

## Task
你正在 GitHub Actions 中作为 Codex 自修复代理运行。
请只在确认是仓库源码、工作流、校验脚本或文档问题时修改代码。
如果日志显示是临时网络、代理订阅不可用、站点短暂限流、GitHub runner 抖动、或者半月完成后的正常跳过，请不要修改文件。

## Repository Rules
- 直接在 main 上修复；禁止 force push。
- 不要启动长时间爬虫；只运行语法校验、workflow 静态校验或很短的 smoke test。
- 修改代码或 workflow 后必须同步 README.md、CHANGELOG.md、HISTORY.md；代理相关还要同步 DOCKER_DEPLOY.md。
- 允许修改的范围：.github/workflows/、custom_scripts/、爬虫脚本、scripts/auto_fix_workflow.py、README/CHANGELOG/HISTORY/AGENTS/部署文档。
- 修复目标是让爬虫 workflow 符合：上午 08:00-12:30，下午 13:00-22:00；长跑自动按 Action 6 小时硬限制和当前时间窗口取更早截止，并保留提交缓冲；每半月完成后跳过。

## Logs
```text
autohome-crawl	Set up job	﻿2026-07-05T17:32:23.2566485Z Current runner version: '2.335.1'
autohome-crawl	Set up job	2026-07-05T17:32:23.2591792Z ##[group]Runner Image Provisioner
autohome-crawl	Set up job	2026-07-05T17:32:23.2592785Z Hosted Compute Agent
autohome-crawl	Set up job	2026-07-05T17:32:23.2593410Z Version: 20260624.560
autohome-crawl	Set up job	2026-07-05T17:32:23.2594108Z Commit: 925d229a51159bc391ae97e54a2dd1fe20af789d
autohome-crawl	Set up job	2026-07-05T17:32:23.2594891Z Build Date: 2026-06-24T18:26:47Z
autohome-crawl	Set up job	2026-07-05T17:32:23.2595633Z Worker ID: {684be12c-df49-4623-a17a-09bdebf38a41}
autohome-crawl	Set up job	2026-07-05T17:32:23.2596450Z Azure Region: westus
autohome-crawl	Set up job	2026-07-05T17:32:23.2597042Z ##[endgroup]
autohome-crawl	Set up job	2026-07-05T17:32:23.2599110Z ##[group]Operating System
autohome-crawl	Set up job	2026-07-05T17:32:23.2599827Z Ubuntu
autohome-crawl	Set up job	2026-07-05T17:32:23.2600412Z 24.04.4
autohome-crawl	Set up job	2026-07-05T17:32:23.2601043Z LTS
autohome-crawl	Set up job	2026-07-05T17:32:23.2601593Z ##[endgroup]
autohome-crawl	Set up job	2026-07-05T17:32:23.2602156Z ##[group]Runner Image
autohome-crawl	Set up job	2026-07-05T17:32:23.2602930Z Image: ubuntu-24.04
autohome-crawl	Set up job	2026-07-05T17:32:23.2603516Z Version: 20260628.225.1
autohome-crawl	Set up job	2026-07-05T17:32:23.2604652Z Included Software: https://github.com/actions/runner-images/blob/ubuntu24/20260628.225/images/ubuntu/Ubuntu2404-Readme.md
autohome-crawl	Set up job	2026-07-05T17:32:23.2606445Z Image Release: https://github.com/actions/runner-images/releases/tag/ubuntu24%2F20260628.225
autohome-crawl	Set up job	2026-07-05T17:32:23.2607473Z ##[endgroup]
autohome-crawl	Set up job	2026-07-05T17:32:23.2608771Z ##[group]GITHUB_TOKEN Permissions
autohome-crawl	Set up job	2026-07-05T17:32:23.2610732Z Contents: write
autohome-crawl	Set up job	2026-07-05T17:32:23.2611378Z Metadata: read
autohome-crawl	Set up job	2026-07-05T17:32:23.2612057Z ##[endgroup]
autohome-crawl	Set up job	2026-07-05T17:32:23.2614103Z Secret source: Actions
autohome-crawl	Set up job	2026-07-05T17:32:23.2614860Z Prepare workflow directory
autohome-crawl	Set up job	2026-07-05T17:32:23.3008718Z Prepare all required actions
autohome-crawl	Set up job	2026-07-05T17:32:23.3049425Z Getting action download info
autohome-crawl	Set up job	2026-07-05T17:32:23.7010688Z Download action repository 'actions/checkout@main' (SHA:4f1f4aec02e41874fa0262ea8ff5172d7978ad1e)
autohome-crawl	Set up job	2026-07-05T17:32:24.0865945Z Download action repository 'actions/setup-python@main' (SHA:ece7cb06caefa5fff74198d8649806c4678c61a1)
autohome-crawl	Set up job	2026-07-05T17:32:24.5600697Z Download action repository 'browser-actions/setup-chrome@v2' (SHA:2e1d749697dd1612b833dba4a722266286fbefcd)
autohome-crawl	Set up job	2026-07-05T17:32:24.8483463Z Download action repository 'nanasess/setup-chromedriver@v2' (SHA:ef5c64a93512d266b23b80bae95e46a67f30e703)
autohome-crawl	Set up job	2026-07-05T17:32:25.1760294Z Download action repository 'actions/cache@main' (SHA:55cc8345863c7cc4c66a329aec7e433d2d1c52a9)
autohome-crawl	Set up job	2026-07-05T17:32:25.7347187Z Download action repository 'actions/upload-artifact@v4' (SHA:ea165f8d65b6e75b540449e92b4886f43607fa02)
autohome-crawl	Set up job	2026-07-05T17:32:26.0086301Z Complete job name: autohome-crawl
autohome-crawl	Run actions/checkout@main	﻿2026-07-05T17:32:26.1337369Z ##[group]Run actions/checkout@main
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1339011Z with:
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1347083Z   token: ***
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1348148Z   repository: Fatty911/crawl_cars
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1349134Z   ssh-strict: true
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1349918Z   ssh-user: git
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1350743Z   persist-credentials: true
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1351633Z   clean: true
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1352459Z   sparse-checkout-cone-mode: true
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1353423Z   fetch-depth: 1
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1354214Z   fetch-tags: false
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1355031Z   show-progress: true
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1355869Z   lfs: false
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1356625Z   submodules: false
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1357462Z   set-safe-directory: true
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1358547Z   allow-unsafe-pr-checkout: false
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1359946Z env:
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1360687Z   RUN_TIME: 10800
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1361503Z   MORNING_RUN_TIME: 10800
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1362392Z   AFTERNOON_RUN_TIME: 21000
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1363306Z   MAX_WORKFLOW_SECONDS: 21600
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1364346Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1365392Z   WINDOW_END_BUFFER_SECONDS: 900
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1366304Z   MAX_CARS: 0
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1367091Z   CRAWL_MIN_DELAY_SECONDS: 3
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1368225Z   CRAWL_MAX_DELAY_SECONDS: 8
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.1369117Z ##[endgroup]
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2449641Z Syncing repository: Fatty911/crawl_cars
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2452261Z ##[group]Getting Git version info
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2453757Z Working directory is '/home/runner/work/crawl_cars/crawl_cars'
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2456276Z [command]/usr/bin/git version
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2559387Z git version 2.54.0
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2583276Z ##[endgroup]
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2595744Z Temporarily overriding HOME='/home/runner/work/_temp/c6059208-ee5f-4127-947c-e0368208665f' before making global git config changes
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2600960Z Adding repository directory to the temporary git global config as a safe directory
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2604891Z [command]/usr/bin/git config --global --add safe.directory /home/runner/work/crawl_cars/crawl_cars
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2657519Z Deleting the contents of '/home/runner/work/crawl_cars/crawl_cars'
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2661296Z ##[group]Determining repository object format
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2663691Z ##[endgroup]
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2665401Z ##[group]Initializing the repository
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2668117Z [command]/usr/bin/git init /home/runner/work/crawl_cars/crawl_cars
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2782577Z hint: Using 'master' as the name for the initial branch. This default branch name
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2784874Z hint: will change to "main" in Git 3.0. To configure the initial branch name
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2788308Z hint: to use in all of your new repositories, which will suppress this warning,
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2790805Z hint: call:
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2791631Z hint:
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2792641Z hint: 	git config --global init.defaultBranch <name>
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2794045Z hint:
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2795337Z hint: Names commonly chosen instead of 'master' are 'main', 'trunk' and
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2797247Z hint: 'development'. The just-created branch can be renamed via this command:
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2798968Z hint:
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2799851Z hint: 	git branch -m <name>
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2801161Z hint:
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2802449Z hint: Disable this message with "git config set advice.defaultBranchName false"
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2805073Z Initialized empty Git repository in /home/runner/work/crawl_cars/crawl_cars/.git/
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2810806Z [command]/usr/bin/git remote add origin https://github.com/Fatty911/crawl_cars
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2857592Z ##[endgroup]
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2860825Z ##[group]Disabling automatic garbage collection
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2863073Z [command]/usr/bin/git config --local gc.auto 0
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2897310Z ##[endgroup]
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2900037Z ##[group]Setting up auth
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2901746Z Removing SSH command configuration
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2904906Z [command]/usr/bin/git config --local --name-only --get-regexp core\.sshCommand
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.2948750Z [command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'core\.sshCommand' && git config --local --unset-all 'core.sshCommand' || :"
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.3374786Z Removing HTTP extra header
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.3382532Z [command]/usr/bin/git config --local --name-only --get-regexp http\.https\:\/\/github\.com\/\.extraheader
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.3424666Z [command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'http\.https\:\/\/github\.com\/\.extraheader' && git config --local --unset-all 'http.https://github.com/.extraheader' || :"
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.3668961Z Removing includeIf entries pointing to credentials config files
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.3677184Z [command]/usr/bin/git config --local --name-only --get-regexp ^includeIf\.gitdir:
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.3724081Z [command]/usr/bin/git submodule foreach --recursive git config --local --show-origin --name-only --get-regexp remote.origin.url
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.3989828Z [command]/usr/bin/git config --file /home/runner/work/_temp/git-credentials-e3f777f1-ebe8-4f6c-8fd5-cb2cd3517f45.config http.https://github.com/.extraheader AUTHORIZATION: basic ***
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.4033868Z [command]/usr/bin/git config --local includeIf.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git.path /home/runner/work/_temp/git-credentials-e3f777f1-ebe8-4f6c-8fd5-cb2cd3517f45.config
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.4071362Z [command]/usr/bin/git config --local includeIf.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git/worktrees/*.path /home/runner/work/_temp/git-credentials-e3f777f1-ebe8-4f6c-8fd5-cb2cd3517f45.config
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.4128148Z [command]/usr/bin/git config --local includeIf.gitdir:/github/workspace/.git.path /github/runner_temp/git-credentials-e3f777f1-ebe8-4f6c-8fd5-cb2cd3517f45.config
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.4165272Z [command]/usr/bin/git config --local includeIf.gitdir:/github/workspace/.git/worktrees/*.path /github/runner_temp/git-credentials-e3f777f1-ebe8-4f6c-8fd5-cb2cd3517f45.config
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.4195357Z ##[endgroup]
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.4196759Z ##[group]Fetching the repository
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.4203151Z [command]/usr/bin/git -c protocol.version=2 fetch --no-tags --prune --no-recurse-submodules --depth=1 origin +18240c947ec83967373af73280d3c10748762bd8:refs/remotes/origin/main
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9084572Z From https://github.com/Fatty911/crawl_cars
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9122409Z  * [new ref]         18240c947ec83967373af73280d3c10748762bd8 -> origin/main
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9128981Z [command]/usr/bin/git branch --list --remote origin/main
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9160875Z   origin/main
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9169669Z [command]/usr/bin/git rev-parse refs/remotes/origin/main
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9195898Z 18240c947ec83967373af73280d3c10748762bd8
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9200466Z ##[endgroup]
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9201206Z ##[group]Determining the checkout info
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9202058Z ##[endgroup]
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9205631Z [command]/usr/bin/git sparse-checkout disable
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9256236Z [command]/usr/bin/git config --local --unset-all extensions.worktreeConfig
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9289313Z ##[group]Checking out the ref
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9293341Z [command]/usr/bin/git checkout --progress --force -B main refs/remotes/origin/main
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9429262Z Switched to a new branch 'main'
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9432623Z branch 'main' set up to track 'origin/main'.
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9439335Z ##[endgroup]
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9487650Z [command]/usr/bin/git log -1 --format=%H
autohome-crawl	Run actions/checkout@main	2026-07-05T17:32:26.9517316Z 18240c947ec83967373af73280d3c10748762bd8
autohome-crawl	Prepare crawl period	﻿2026-07-05T17:32:26.9719630Z ##[group]Run mkdir -p crawl_state
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9720097Z ^[[36;1mmkdir -p crawl_state^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9720446Z ^[[36;1mCN_DAY=$(TZ=Asia/Shanghai date +%d)^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9720843Z ^[[36;1mCN_MONTH=$(TZ=Asia/Shanghai date +%Y%m)^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9721210Z ^[[36;1mif [ $((10#$CN_DAY)) -le 15 ]; then^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9721549Z ^[[36;1m  CRAWL_PERIOD="${CN_MONTH}_H1"^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9721862Z ^[[36;1melse^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9722127Z ^[[36;1m  CRAWL_PERIOD="${CN_MONTH}_H2"^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9722432Z ^[[36;1mfi^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9722760Z ^[[36;1mDONE_MARKER="crawl_state/autohome_${CRAWL_PERIOD}.done"^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9723251Z ^[[36;1mCURRENT_PERIOD_FILE="crawl_state/autohome_current_period"^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9723727Z ^[[36;1mecho "WORKFLOW_START_EPOCH=$(date +%s)" >> $GITHUB_ENV^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9724164Z ^[[36;1mecho "CRAWL_PERIOD=$CRAWL_PERIOD" >> $GITHUB_ENV^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9724622Z ^[[36;1mecho "AUTOHOME_DONE_MARKER=$DONE_MARKER" >> $GITHUB_ENV^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9725057Z ^[[36;1m^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9725313Z ^[[36;1mFORCE_RESTART="${FORCE_RESTART}"^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9725647Z ^[[36;1mDEBUG_MODE="${DEBUG_MODE}"^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9725949Z ^[[36;1m^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9726208Z ^[[36;1mif [ "$FORCE_RESTART" = "true" ]; then^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9726563Z ^[[36;1m  rm -f "$DONE_MARKER"^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9726854Z ^[[36;1mfi^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9727087Z ^[[36;1m^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9727491Z ^[[36;1mif [ "$FORCE_RESTART" != "true" ] && [ "$DEBUG_MODE" != "true" ] && [ -f "$DONE_MARKER" ]; then^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9728314Z ^[[36;1m  echo "$CRAWL_PERIOD 已完成全量汽车之家爬取，本半月不再爬取"^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9728696Z ^[[36;1m  echo "SKIP_CRAWL=true" >> $GITHUB_ENV^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9729057Z ^[[36;1m  echo "skip=true" >> $GITHUB_OUTPUT^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9729398Z ^[[36;1m  exit 0^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9729654Z ^[[36;1mfi^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9730139Z ^[[36;1mecho "INCREMENTAL_MODE=true" >> $GITHUB_ENV^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9730488Z ^[[36;1m^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9730989Z ^[[36;1mif [ "$FORCE_RESTART" = "true" ] || [ ! -f "$CURRENT_PERIOD_FILE" ] || [ "$(cat "$CURRENT_PERIOD_FILE")" != "$CRAWL_PERIOD" ]; then^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9731636Z ^[[36;1m  echo "进入新的半月周期 $CRAWL_PERIOD，启用增量模式（保留已有HTML）"^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9732056Z ^[[36;1m  rm -f progress.json step1_done^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9732394Z ^[[36;1mfi^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9732695Z ^[[36;1mecho "$CRAWL_PERIOD" > "$CURRENT_PERIOD_FILE"^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9733089Z ^[[36;1mecho "SKIP_CRAWL=false" >> $GITHUB_ENV^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9733459Z ^[[36;1mecho "skip=false" >> $GITHUB_OUTPUT^[[0m
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9946111Z shell: /usr/bin/bash -e {0}
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9946527Z env:
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9946813Z   RUN_TIME: 10800
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9947125Z   MORNING_RUN_TIME: 10800
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9947477Z   AFTERNOON_RUN_TIME: 21000
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9948160Z   MAX_WORKFLOW_SECONDS: 21600
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9948577Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9948987Z   WINDOW_END_BUFFER_SECONDS: 900
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9949335Z   MAX_CARS: 0
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9949631Z   CRAWL_MIN_DELAY_SECONDS: 3
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9950001Z   CRAWL_MAX_DELAY_SECONDS: 8
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9950344Z   FORCE_RESTART: false
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9950653Z   DEBUG_MODE: true
autohome-crawl	Prepare crawl period	2026-07-05T17:32:26.9950946Z ##[endgroup]
autohome-crawl	Configure crawl window	﻿2026-07-05T17:32:27.0226107Z ##[group]Run if [ "$DEBUG_MODE" = "true" ]; then
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0226590Z ^[[36;1mif [ "$DEBUG_MODE" = "true" ]; then^[[0m
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0226965Z ^[[36;1m  echo "调试模式：跳过时间窗口限制，每次最多爬30车型"^[[0m
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0227329Z ^[[36;1m  echo "MAX_CARS=30" >> "$GITHUB_ENV"^[[0m
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0227711Z ^[[36;1m  echo "skip=false" >> "$GITHUB_OUTPUT"^[[0m
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0228366Z ^[[36;1melse^[[0m
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0228698Z ^[[36;1m  python custom_scripts/crawl_budget.py configure^[[0m
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0229096Z ^[[36;1m  echo "MAX_CARS=0" >> "$GITHUB_ENV"^[[0m
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0229498Z ^[[36;1m  echo "skip=false" >> "$GITHUB_OUTPUT"^[[0m
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0229838Z ^[[36;1mfi^[[0m
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0261872Z shell: /usr/bin/bash -e {0}
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0262195Z env:
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0262437Z   RUN_TIME: 10800
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0262708Z   MORNING_RUN_TIME: 10800
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0263001Z   AFTERNOON_RUN_TIME: 21000
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0263300Z   MAX_WORKFLOW_SECONDS: 21600
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0263671Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0264012Z   WINDOW_END_BUFFER_SECONDS: 900
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0264313Z   MAX_CARS: 0
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0264568Z   CRAWL_MIN_DELAY_SECONDS: 3
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0264871Z   CRAWL_MAX_DELAY_SECONDS: 8
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0265170Z   WORKFLOW_START_EPOCH: 1783272747
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0265492Z   CRAWL_PERIOD: 202607_H1
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0265847Z   AUTOHOME_DONE_MARKER: crawl_state/autohome_202607_H1.done
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0266241Z   INCREMENTAL_MODE: true
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0266530Z   SKIP_CRAWL: false
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0266797Z   PROFILE_INPUT: auto
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0267057Z   DEBUG_MODE: true
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0267316Z ##[endgroup]
autohome-crawl	Configure crawl window	2026-07-05T17:32:27.0318130Z 调试模式：跳过时间窗口限制，每次最多爬30车型
autohome-crawl	Calculate delay from trigger time	﻿2026-07-05T17:32:27.0382160Z ##[group]Run echo "外部触发已经在 08:30/13:30 左右执行，不再追加随机启动延迟"
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0382628Z ^[[36;1mecho "外部触发已经在 08:30/13:30 左右执行，不再追加随机启动延迟"^[[0m
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0383008Z ^[[36;1mecho "delay=0" >> "$GITHUB_OUTPUT"^[[0m
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0412338Z shell: /usr/bin/bash -e {0}
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0412667Z env:
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0412904Z   RUN_TIME: 10800
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0413181Z   MORNING_RUN_TIME: 10800
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0413473Z   AFTERNOON_RUN_TIME: 21000
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0413774Z   MAX_WORKFLOW_SECONDS: 21600
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0414086Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0414419Z   WINDOW_END_BUFFER_SECONDS: 900
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0414713Z   MAX_CARS: 30
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0414970Z   CRAWL_MIN_DELAY_SECONDS: 3
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0415454Z   CRAWL_MAX_DELAY_SECONDS: 8
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0415761Z   WORKFLOW_START_EPOCH: 1783272747
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0416068Z   CRAWL_PERIOD: 202607_H1
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0416457Z   AUTOHOME_DONE_MARKER: crawl_state/autohome_202607_H1.done
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0416888Z   INCREMENTAL_MODE: true
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0417172Z   SKIP_CRAWL: false
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0417429Z ##[endgroup]
autohome-crawl	Calculate delay from trigger time	2026-07-05T17:32:27.0467404Z 外部触发已经在 08:30/13:30 左右执行，不再追加随机启动延迟
autohome-crawl	Random delay	﻿2026-07-05T17:32:27.0521214Z ##[group]Run DELAY="0"
autohome-crawl	Random delay	2026-07-05T17:32:27.0521571Z ^[[36;1mDELAY="0"^[[0m
autohome-crawl	Random delay	2026-07-05T17:32:27.0521904Z ^[[36;1mif [ "$DELAY" != "0" ] && [ -n "$DELAY" ]; then^[[0m
autohome-crawl	Random delay	2026-07-05T17:32:27.0522363Z ^[[36;1m  echo "Waiting $DELAY seconds ($(($DELAY / 60)) minutes)..."^[[0m
autohome-crawl	Random delay	2026-07-05T17:32:27.0522797Z ^[[36;1m  sleep $DELAY^[[0m
autohome-crawl	Random delay	2026-07-05T17:32:27.0523085Z ^[[36;1melse^[[0m
autohome-crawl	Random delay	2026-07-05T17:32:27.0523343Z ^[[36;1m  echo "跳过延迟"^[[0m
autohome-crawl	Random delay	2026-07-05T17:32:27.0523611Z ^[[36;1mfi^[[0m
autohome-crawl	Random delay	2026-07-05T17:32:27.0552991Z shell: /usr/bin/bash -e {0}
autohome-crawl	Random delay	2026-07-05T17:32:27.0553332Z env:
autohome-crawl	Random delay	2026-07-05T17:32:27.0553576Z   RUN_TIME: 10800
autohome-crawl	Random delay	2026-07-05T17:32:27.0553850Z   MORNING_RUN_TIME: 10800
autohome-crawl	Random delay	2026-07-05T17:32:27.0554145Z   AFTERNOON_RUN_TIME: 21000
autohome-crawl	Random delay	2026-07-05T17:32:27.0554444Z   MAX_WORKFLOW_SECONDS: 21600
autohome-crawl	Random delay	2026-07-05T17:32:27.0554764Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
autohome-crawl	Random delay	2026-07-05T17:32:27.0555109Z   WINDOW_END_BUFFER_SECONDS: 900
autohome-crawl	Random delay	2026-07-05T17:32:27.0555414Z   MAX_CARS: 30
autohome-crawl	Random delay	2026-07-05T17:32:27.0555681Z   CRAWL_MIN_DELAY_SECONDS: 3
autohome-crawl	Random delay	2026-07-05T17:32:27.0556018Z   CRAWL_MAX_DELAY_SECONDS: 8
autohome-crawl	Random delay	2026-07-05T17:32:27.0556313Z   WORKFLOW_START_EPOCH: 1783272747
autohome-crawl	Random delay	2026-07-05T17:32:27.0556637Z   CRAWL_PERIOD: 202607_H1
autohome-crawl	Random delay	2026-07-05T17:32:27.0556993Z   AUTOHOME_DONE_MARKER: crawl_state/autohome_202607_H1.done
autohome-crawl	Random delay	2026-07-05T17:32:27.0557393Z   INCREMENTAL_MODE: true
autohome-crawl	Random delay	2026-07-05T17:32:27.0557685Z   SKIP_CRAWL: false
autohome-crawl	Random delay	2026-07-05T17:32:27.0558312Z ##[endgroup]
autohome-crawl	Random delay	2026-07-05T17:32:27.0610600Z 跳过延迟
autohome-crawl	Run actions/setup-python@main	﻿2026-07-05T17:32:27.0697622Z ##[group]Run actions/setup-python@main
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0698396Z with:
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0698695Z   python-version: 3.12
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0698991Z   check-latest: false
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0701321Z   token: ***
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0701589Z   update-environment: true
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0701892Z   allow-prereleases: false
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0702187Z   freethreaded: false
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0702457Z env:
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0702695Z   RUN_TIME: 10800
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0702953Z   MORNING_RUN_TIME: 10800
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0703242Z   AFTERNOON_RUN_TIME: 21000
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0703535Z   MAX_WORKFLOW_SECONDS: 21600
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0703846Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0704183Z   WINDOW_END_BUFFER_SECONDS: 900
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0704479Z   MAX_CARS: 30
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0704739Z   CRAWL_MIN_DELAY_SECONDS: 3
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0705030Z   CRAWL_MAX_DELAY_SECONDS: 8
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0705329Z   WORKFLOW_START_EPOCH: 1783272747
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0705640Z   CRAWL_PERIOD: 202607_H1
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0706012Z   AUTOHOME_DONE_MARKER: crawl_state/autohome_202607_H1.done
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0706401Z   INCREMENTAL_MODE: true
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0706682Z   SKIP_CRAWL: false
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.0706936Z ##[endgroup]
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.1980533Z ##[group]Installed versions
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.2083846Z Successfully set up CPython (3.12.13)
autohome-crawl	Run actions/setup-python@main	2026-07-05T17:32:27.2084895Z ##[endgroup]
autohome-crawl	Run browser-actions/setup-chrome@v2	﻿2026-07-05T17:32:27.2287256Z ##[group]Run browser-actions/setup-chrome@v2
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2288103Z with:
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2288505Z   chrome-version: stable
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2288982Z   install-dependencies: false
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2289479Z   install-chromedriver: false
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2289946Z   no-sudo: false
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2290396Z env:
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2290754Z   RUN_TIME: 10800
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2291172Z   MORNING_RUN_TIME: 10800
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2291623Z   AFTERNOON_RUN_TIME: 21000
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2292089Z   MAX_WORKFLOW_SECONDS: 21600
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2292587Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2293117Z   WINDOW_END_BUFFER_SECONDS: 900
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2293826Z   MAX_CARS: 30
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2294231Z   CRAWL_MIN_DELAY_SECONDS: 3
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2294701Z   CRAWL_MAX_DELAY_SECONDS: 8
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2295174Z   WORKFLOW_START_EPOCH: 1783272747
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2295690Z   CRAWL_PERIOD: 202607_H1
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2296244Z   AUTOHOME_DONE_MARKER: crawl_state/autohome_202607_H1.done
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2296911Z   INCREMENTAL_MODE: true
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2297356Z   SKIP_CRAWL: false
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2298138Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2298980Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2299785Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2300516Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2301237Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2301970Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.2302597Z ##[endgroup]
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.3125557Z Setup chrome stable
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.3135811Z Attempting to download chrome stable...
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:27.3431814Z Acquiring chrome stable from https://storage.googleapis.com/chrome-for-testing-public/150.0.7871.46/linux64/chrome-linux64.zip
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:28.6174300Z Installing chrome...
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:28.6215267Z [command]/usr/bin/unzip -o -q /home/runner/work/_temp/dbf6f6c7-03bd-41a7-a4ff-ef650d04991a
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:32.3595590Z Successfully Installed chrome to /opt/hostedtoolcache/setup-chrome/chrome/stable/x64
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:32.3603924Z [command]/opt/hostedtoolcache/setup-chrome/chrome/stable/x64/chrome --version
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:32.7043160Z Google Chrome for Testing 150.0.7871.46 
autohome-crawl	Run browser-actions/setup-chrome@v2	2026-07-05T17:32:32.7271982Z Successfully setup chrome 150.0.7871.46
autohome-crawl	Run nanasess/setup-chromedriver@v2	﻿2026-07-05T17:32:32.7428611Z ##[group]Run nanasess/setup-chromedriver@v2
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7429026Z with:
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7429233Z env:
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7429440Z   RUN_TIME: 10800
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7429663Z   MORNING_RUN_TIME: 10800
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7429914Z   AFTERNOON_RUN_TIME: 21000
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7430156Z   MAX_WORKFLOW_SECONDS: 21600
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7430433Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7430712Z   WINDOW_END_BUFFER_SECONDS: 900
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7430984Z   MAX_CARS: 30
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7431190Z   CRAWL_MIN_DELAY_SECONDS: 3
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7431434Z   CRAWL_MAX_DELAY_SECONDS: 8
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7431676Z   WORKFLOW_START_EPOCH: 1783272747
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7431930Z   CRAWL_PERIOD: 202607_H1
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7432223Z   AUTOHOME_DONE_MARKER: crawl_state/autohome_202607_H1.done
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7432566Z   INCREMENTAL_MODE: true
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7432801Z   SKIP_CRAWL: false
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7433097Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7433568Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7434001Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7434403Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7434801Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7435188Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.7435539Z ##[endgroup]
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.8072851Z ##setup chromedriver
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:32.8092629Z [command]/home/runner/work/_actions/nanasess/setup-chromedriver/v2/lib/setup-chromedriver.sh  linux64 
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:34.5055375Z CHROME_VERSION=149
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:34.5326385Z VERSION=149.0.7827.200
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:34.5328079Z Downloading https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json...
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:34.7708793Z Falling back to latest version of ChromeDriver for linux64
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:34.7727385Z VERSION3=149.0.7827
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:34.9425602Z VERSION=149.0.7827.155
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:35.1081152Z Installing ChromeDriver 149.0.7827.155 for linux64
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:35.1083648Z Downloading https://storage.googleapis.com/chrome-for-testing-public/149.0.7827.155/linux64/chromedriver-linux64.zip...
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:35.3737463Z Installing chromedriver to /usr/local/bin
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:35.3850612Z Chrome version:
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:35.4119143Z Google Chrome 149.0.7827.200 
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:35.4125495Z Chromedriver version:
autohome-crawl	Run nanasess/setup-chromedriver@v2	2026-07-05T17:32:35.4172302Z ChromeDriver 149.0.7827.155 (07b52360cc15066f987c910ab34dfbcd4a8778d2-refs/branch-heads/7827@{#3246})
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	﻿2026-07-05T17:32:35.4320754Z ##[group]Run pip install requests beautifulsoup4 selenium lxml PyYAML
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4321323Z ^[[36;1mpip install requests beautifulsoup4 selenium lxml PyYAML^[[0m
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4358890Z shell: /usr/bin/bash -e {0}
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4359159Z env:
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4359358Z   RUN_TIME: 10800
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4359575Z   MORNING_RUN_TIME: 10800
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4359816Z   AFTERNOON_RUN_TIME: 21000
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4360058Z   MAX_WORKFLOW_SECONDS: 21600
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4360333Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4360612Z   WINDOW_END_BUFFER_SECONDS: 900
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4360878Z   MAX_CARS: 30
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4361094Z   CRAWL_MIN_DELAY_SECONDS: 3
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4361334Z   CRAWL_MAX_DELAY_SECONDS: 8
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4361576Z   WORKFLOW_START_EPOCH: 1783272747
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4361830Z   CRAWL_PERIOD: 202607_H1
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4362124Z   AUTOHOME_DONE_MARKER: crawl_state/autohome_202607_H1.done
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4362465Z   INCREMENTAL_MODE: true
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4362730Z   SKIP_CRAWL: false
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4363011Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4363453Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4363894Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4364283Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4364679Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4365076Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:35.4365417Z ##[endgroup]
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.3668597Z Collecting requests
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.4168487Z   Downloading requests-2.34.2-py3-none-any.whl.metadata (4.8 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.4336312Z Collecting beautifulsoup4
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.4363351Z   Downloading beautifulsoup4-4.15.0-py3-none-any.whl.metadata (3.8 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.4638291Z Collecting selenium
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.4664884Z   Downloading selenium-4.45.0-py3-none-any.whl.metadata (7.4 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.6933245Z Collecting lxml
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.6963340Z   Downloading lxml-6.1.1-cp312-cp312-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl.metadata (3.5 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.7325270Z Collecting PyYAML
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.7355707Z   Downloading pyyaml-6.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (2.4 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.8231552Z Collecting charset_normalizer<4,>=2 (from requests)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.8263691Z   Downloading charset_normalizer-3.4.7-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl.metadata (40 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.8448753Z Collecting idna<4,>=2.5 (from requests)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.8475112Z   Downloading idna-3.18-py3-none-any.whl.metadata (6.1 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.8675677Z Collecting urllib3<3,>=1.26 (from requests)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.8702399Z   Downloading urllib3-2.7.0-py3-none-any.whl.metadata (6.9 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.8863523Z Collecting certifi>=2023.5.7 (from requests)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.8891071Z   Downloading certifi-2026.6.17-py3-none-any.whl.metadata (2.5 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.9064240Z Collecting soupsieve>=1.6.1 (from beautifulsoup4)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.9088541Z   Downloading soupsieve-2.8.4-py3-none-any.whl.metadata (4.6 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.9251810Z Collecting typing-extensions>=4.0.0 (from beautifulsoup4)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.9275294Z   Downloading typing_extensions-4.16.0-py3-none-any.whl.metadata (3.3 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.9412843Z Collecting trio<1.0,>=0.31.0 (from selenium)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.9436529Z   Downloading trio-0.33.0-py3-none-any.whl.metadata (8.5 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.9548396Z Collecting trio-websocket<1.0,>=0.12.2 (from selenium)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.9575257Z   Downloading trio_websocket-0.12.2-py3-none-any.whl.metadata (5.1 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.9761413Z Collecting websocket-client<2.0,>=1.8.0 (from selenium)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.9794632Z   Downloading websocket_client-1.9.0-py3-none-any.whl.metadata (8.3 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.9943787Z Collecting attrs>=23.2.0 (from trio<1.0,>=0.31.0->selenium)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:36.9972476Z   Downloading attrs-26.1.0-py3-none-any.whl.metadata (8.8 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.0122410Z Collecting sortedcontainers (from trio<1.0,>=0.31.0->selenium)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.0152415Z   Downloading sortedcontainers-2.4.0-py2.py3-none-any.whl.metadata (10 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.0272149Z Collecting outcome (from trio<1.0,>=0.31.0->selenium)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.0298604Z   Downloading outcome-1.3.0.post0-py2.py3-none-any.whl.metadata (2.6 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.0393601Z Collecting sniffio>=1.3.0 (from trio<1.0,>=0.31.0->selenium)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.0420396Z   Downloading sniffio-1.3.1-py3-none-any.whl.metadata (3.9 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.0558096Z Collecting wsproto>=0.14 (from trio-websocket<1.0,>=0.12.2->selenium)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.0587198Z   Downloading wsproto-1.3.2-py3-none-any.whl.metadata (5.2 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.0728905Z Collecting pysocks!=1.5.7,<2.0,>=1.5.6 (from urllib3[socks]<3.0,>=2.6.3->selenium)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.0759070Z   Downloading PySocks-1.7.1-py3-none-any.whl.metadata (13 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.0922994Z Collecting h11<1,>=0.16.0 (from wsproto>=0.14->trio-websocket<1.0,>=0.12.2->selenium)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.0952203Z   Downloading h11-0.16.0-py3-none-any.whl.metadata (8.3 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.1029723Z Downloading requests-2.34.2-py3-none-any.whl (73 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.1082560Z Downloading charset_normalizer-3.4.7-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (216 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.1157502Z Downloading idna-3.18-py3-none-any.whl (65 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.1224571Z Downloading urllib3-2.7.0-py3-none-any.whl (131 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.1276495Z Downloading beautifulsoup4-4.15.0-py3-none-any.whl (109 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.1351350Z Downloading selenium-4.45.0-py3-none-any.whl (9.5 MB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.1816124Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 9.5/9.5 MB 216.3 MB/s  0:00:00
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.1846042Z Downloading trio-0.33.0-py3-none-any.whl (510 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.1906544Z Downloading trio_websocket-0.12.2-py3-none-any.whl (21 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.1952640Z Downloading typing_extensions-4.16.0-py3-none-any.whl (45 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.1999818Z Downloading PySocks-1.7.1-py3-none-any.whl (16 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.2047105Z Downloading websocket_client-1.9.0-py3-none-any.whl (82 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.2097810Z Downloading lxml-6.1.1-cp312-cp312-manylinux_2_26_x86_64.manylinux_2_28_x86_64.whl (5.2 MB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.2306404Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 5.2/5.2 MB 275.9 MB/s  0:00:00
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.2333328Z Downloading pyyaml-6.0.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl (807 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.2390862Z    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 807.9/807.9 kB 153.5 MB/s  0:00:00
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.2417773Z Downloading attrs-26.1.0-py3-none-any.whl (67 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.2464496Z Downloading certifi-2026.6.17-py3-none-any.whl (133 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.2513004Z Downloading outcome-1.3.0.post0-py2.py3-none-any.whl (10 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.2556629Z Downloading sniffio-1.3.1-py3-none-any.whl (10 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.2604057Z Downloading soupsieve-2.8.4-py3-none-any.whl (37 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.2649957Z Downloading wsproto-1.3.2-py3-none-any.whl (24 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.2694862Z Downloading h11-0.16.0-py3-none-any.whl (37 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.2740436Z Downloading sortedcontainers-2.4.0-py2.py3-none-any.whl (29 kB)
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:37.3538459Z Installing collected packages: sortedcontainers, websocket-client, urllib3, typing-extensions, soupsieve, sniffio, PyYAML, pysocks, lxml, idna, h11, charset_normalizer, certifi, attrs, wsproto, requests, outcome, beautifulsoup4, trio, trio-websocket, selenium
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:39.4526387Z 
autohome-crawl	Run pip install requests beautifulsoup4 selenium lxml PyYAML	2026-07-05T17:32:39.4552855Z Successfully installed PyYAML-6.0.3 attrs-26.1.0 beautifulsoup4-4.15.0 certifi-2026.6.17 charset_normalizer-3.4.7 h11-0.16.0 idna-3.18 lxml-6.1.1 outcome-1.3.0.post0 pysocks-1.7.1 requests-2.34.2 selenium-4.45.0 sniffio-1.3.1 sortedcontainers-2.4.0 soupsieve-2.8.4 trio-0.33.0 trio-websocket-0.12.2 typing-extensions-4.16.0 urllib3-2.7.0 websocket-client-1.9.0 wsproto-1.3.2
autohome-crawl	Setup environment	﻿2026-07-05T17:32:39.5390004Z ##[group]Run echo "PYTHONUNBUFFERED=1" >> $GITHUB_ENV
autohome-crawl	Setup environment	2026-07-05T17:32:39.5390730Z ^[[36;1mecho "PYTHONUNBUFFERED=1" >> $GITHUB_ENV^[[0m
autohome-crawl	Setup environment	2026-07-05T17:32:39.5391283Z ^[[36;1mecho "MINIMAX_API_KEY=*** secrets.MINIMAX_API_KEY }}" >> $GITHUB_ENV^[[0m
autohome-crawl	Setup environment	2026-07-05T17:32:39.5391782Z ^[[36;1mecho "ZEN_API_KEY=*** secrets.ZEN_API_KEY }}" >> $GITHUB_ENV^[[0m
autohome-crawl	Setup environment	2026-07-05T17:32:39.5392198Z ^[[36;1mecho "XAI_API_KEY=*** secrets.XAI_API_KEY }}" >> $GITHUB_ENV^[[0m
autohome-crawl	Setup environment	2026-07-05T17:32:39.5392666Z ^[[36;1mecho "OPENROUTER_API_KEY=*** secrets.OPENROUTER_API_KEY }}" >> $GITHUB_ENV^[[0m
autohome-crawl	Setup environment	2026-07-05T17:32:39.5393606Z ^[[36;1mecho "ACTION_PAT=***" >> $GITHUB_ENV^[[0m
autohome-crawl	Setup environment	2026-07-05T17:32:39.5429666Z shell: /usr/bin/bash -e {0}
autohome-crawl	Setup environment	2026-07-05T17:32:39.5429954Z env:
autohome-crawl	Setup environment	2026-07-05T17:32:39.5430169Z   RUN_TIME: 10800
autohome-crawl	Setup environment	2026-07-05T17:32:39.5430407Z   MORNING_RUN_TIME: 10800
autohome-crawl	Setup environment	2026-07-05T17:32:39.5430660Z   AFTERNOON_RUN_TIME: 21000
autohome-crawl	Setup environment	2026-07-05T17:32:39.5430912Z   MAX_WORKFLOW_SECONDS: 21600
autohome-crawl	Setup environment	2026-07-05T17:32:39.5431187Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
autohome-crawl	Setup environment	2026-07-05T17:32:39.5431526Z   WINDOW_END_BUFFER_SECONDS: 900
autohome-crawl	Setup environment	2026-07-05T17:32:39.5431786Z   MAX_CARS: 30
autohome-crawl	Setup environment	2026-07-05T17:32:39.5432006Z   CRAWL_MIN_DELAY_SECONDS: 3
autohome-crawl	Setup environment	2026-07-05T17:32:39.5432256Z   CRAWL_MAX_DELAY_SECONDS: 8
autohome-crawl	Setup environment	2026-07-05T17:32:39.5432535Z   WORKFLOW_START_EPOCH: 1783272747
autohome-crawl	Setup environment	2026-07-05T17:32:39.5432818Z   CRAWL_PERIOD: 202607_H1
autohome-crawl	Setup environment	2026-07-05T17:32:39.5433134Z   AUTOHOME_DONE_MARKER: crawl_state/autohome_202607_H1.done
autohome-crawl	Setup environment	2026-07-05T17:32:39.5433484Z   INCREMENTAL_MODE: true
autohome-crawl	Setup environment	2026-07-05T17:32:39.5433736Z   SKIP_CRAWL: false
autohome-crawl	Setup environment	2026-07-05T17:32:39.5434034Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Setup environment	2026-07-05T17:32:39.5434483Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
autohome-crawl	Setup environment	2026-07-05T17:32:39.5434918Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Setup environment	2026-07-05T17:32:39.5435310Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Setup environment	2026-07-05T17:32:39.5435732Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Setup environment	2026-07-05T17:32:39.5436135Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
autohome-crawl	Setup environment	2026-07-05T17:32:39.5436495Z ##[endgroup]
autohome-crawl	Setup proxy if configured	﻿2026-07-05T17:32:39.5531878Z ##[group]Run python custom_scripts/setup_proxy_runtime.py --github-env "$GITHUB_ENV"
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5532514Z ^[[36;1mpython custom_scripts/setup_proxy_runtime.py --github-env "$GITHUB_ENV"^[[0m
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5565205Z shell: /usr/bin/bash -e {0}
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5565484Z env:
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5565675Z   RUN_TIME: 10800
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5565893Z   MORNING_RUN_TIME: 10800
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5566136Z   AFTERNOON_RUN_TIME: 21000
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5566377Z   MAX_WORKFLOW_SECONDS: 21600
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5566632Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5566911Z   WINDOW_END_BUFFER_SECONDS: 900
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5567153Z   MAX_CARS: 30
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5567363Z   CRAWL_MIN_DELAY_SECONDS: 3
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5567598Z   CRAWL_MAX_DELAY_SECONDS: 8
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5568107Z   WORKFLOW_START_EPOCH: 1783272747
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5568372Z   CRAWL_PERIOD: 202607_H1
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5568667Z   AUTOHOME_DONE_MARKER: crawl_state/autohome_202607_H1.done
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5569039Z   INCREMENTAL_MODE: true
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5569262Z   SKIP_CRAWL: false
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5569717Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5570167Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5570638Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5571088Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5571475Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5571876Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5572223Z   PYTHONUNBUFFERED: 1
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5572478Z   MINIMAX_API_KEY: *** secrets.MINIMAX_API_KEY }}
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5572786Z   ZEN_API_KEY: *** secrets.ZEN_API_KEY }}
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5573073Z   XAI_API_KEY: *** secrets.XAI_API_KEY }}
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5573411Z   OPENROUTER_API_KEY: *** secrets.OPENROUTER_API_KEY }}
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5573925Z   ACTION_PAT: ***
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5574368Z   PROXY_SUBSCRIPTIONS: ***
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.5574613Z ##[endgroup]
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.8407530Z Traceback (most recent call last):
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.8416526Z   File "/home/runner/work/crawl_cars/crawl_cars/custom_scripts/setup_proxy_runtime.py", line 27, in <module>
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.8417468Z     from generate_clash_config import ClashConfigGenerator, redact_url
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.8418465Z ModuleNotFoundError: No module named 'generate_clash_config'
autohome-crawl	Setup proxy if configured	2026-07-05T17:32:39.8637453Z ##[error]Process completed with exit code 1.
autohome-crawl	Disable proxy for GitHub artifact upload	﻿2026-07-05T17:32:39.8834080Z ##[group]Run {
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8834353Z ^[[36;1m{^[[0m
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8834559Z ^[[36;1m  echo "HTTP_PROXY="^[[0m
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8834819Z ^[[36;1m  echo "HTTPS_PROXY="^[[0m
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8835068Z ^[[36;1m  echo "ALL_PROXY="^[[0m
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8835322Z ^[[36;1m  echo "http_proxy="^[[0m
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8835558Z ^[[36;1m  echo "https_proxy="^[[0m
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8835796Z ^[[36;1m  echo "all_proxy="^[[0m
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8836088Z ^[[36;1m} >> "$GITHUB_ENV"^[[0m
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8869265Z shell: /usr/bin/bash -e {0}
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8869527Z env:
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8869724Z   RUN_TIME: 10800
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8869939Z   MORNING_RUN_TIME: 10800
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8870172Z   AFTERNOON_RUN_TIME: 21000
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8870410Z   MAX_WORKFLOW_SECONDS: 21600
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8870666Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8870962Z   WINDOW_END_BUFFER_SECONDS: 900
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8871209Z   MAX_CARS: 30
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8871417Z   CRAWL_MIN_DELAY_SECONDS: 3
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8871718Z   CRAWL_MAX_DELAY_SECONDS: 8
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8871958Z   WORKFLOW_START_EPOCH: 1783272747
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8872221Z   CRAWL_PERIOD: 202607_H1
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8872516Z   AUTOHOME_DONE_MARKER: crawl_state/autohome_202607_H1.done
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8872856Z   INCREMENTAL_MODE: true
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8873088Z   SKIP_CRAWL: false
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8873364Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8873795Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8874233Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8874629Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8875028Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8875419Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8875759Z   PYTHONUNBUFFERED: 1
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8876015Z   MINIMAX_API_KEY: *** secrets.MINIMAX_API_KEY }}
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8876347Z   ZEN_API_KEY: *** secrets.ZEN_API_KEY }}
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8876644Z   XAI_API_KEY: *** secrets.XAI_API_KEY }}
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8876968Z   OPENROUTER_API_KEY: *** secrets.OPENROUTER_API_KEY }}
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8877516Z   ACTION_PAT: ***
autohome-crawl	Disable proxy for GitHub artifact upload	2026-07-05T17:32:39.8877947Z ##[endgroup]
autohome-crawl	Upload error log	﻿2026-07-05T17:32:39.8986857Z Node 20 is being deprecated. This workflow is running with Node 24 by default. If you need to temporarily use Node 20, you can set the ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true environment variable. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/
autohome-crawl	Upload error log	2026-07-05T17:32:39.8988767Z ##[group]Run actions/upload-artifact@v4
autohome-crawl	Upload error log	2026-07-05T17:32:39.8989055Z with:
autohome-crawl	Upload error log	2026-07-05T17:32:39.8989275Z   name: error-log
autohome-crawl	Upload error log	2026-07-05T17:32:39.8989523Z   path: step1_error.log
autohome-crawl	Upload error log	remaining_error.log
autohome-crawl	Upload error log	
autohome-crawl	Upload error log	2026-07-05T17:32:39.8989855Z   if-no-files-found: ignore
autohome-crawl	Upload error log	2026-07-05T17:32:39.8990102Z   retention-days: 7
autohome-crawl	Upload error log	2026-07-05T17:32:39.8990316Z   compression-level: 6
autohome-crawl	Upload error log	2026-07-05T17:32:39.8990538Z   overwrite: false
autohome-crawl	Upload error log	2026-07-05T17:32:39.8990757Z   include-hidden-files: false
autohome-crawl	Upload error log	2026-07-05T17:32:39.8990995Z env:
autohome-crawl	Upload error log	2026-07-05T17:32:39.8991184Z   RUN_TIME: 10800
autohome-crawl	Upload error log	2026-07-05T17:32:39.8991395Z   MORNING_RUN_TIME: 10800
autohome-crawl	Upload error log	2026-07-05T17:32:39.8991622Z   AFTERNOON_RUN_TIME: 21000
autohome-crawl	Upload error log	2026-07-05T17:32:39.8991883Z   MAX_WORKFLOW_SECONDS: 21600
autohome-crawl	Upload error log	2026-07-05T17:32:39.8992135Z   PROGRESS_COMMIT_BUFFER_SECONDS: 1800
autohome-crawl	Upload error log	2026-07-05T17:32:39.8992409Z   WINDOW_END_BUFFER_SECONDS: 900
autohome-crawl	Upload error log	2026-07-05T17:32:39.8992658Z   MAX_CARS: 30
autohome-crawl	Upload error log	2026-07-05T17:32:39.8992858Z   CRAWL_MIN_DELAY_SECONDS: 3
autohome-crawl	Upload error log	2026-07-05T17:32:39.8993096Z   CRAWL_MAX_DELAY_SECONDS: 8
autohome-crawl	Upload error log	2026-07-05T17:32:39.8993331Z   WORKFLOW_START_EPOCH: 1783272747
autohome-crawl	Upload error log	2026-07-05T17:32:39.8993586Z   CRAWL_PERIOD: 202607_H1
autohome-crawl	Upload error log	2026-07-05T17:32:39.8993867Z   AUTOHOME_DONE_MARKER: crawl_state/autohome_202607_H1.done
autohome-crawl	Upload error log	2026-07-05T17:32:39.8994196Z   INCREMENTAL_MODE: true
autohome-crawl	Upload error log	2026-07-05T17:32:39.8994421Z   SKIP_CRAWL: false
autohome-crawl	Upload error log	2026-07-05T17:32:39.8994688Z   pythonLocation: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Upload error log	2026-07-05T17:32:39.8995110Z   PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib/pkgconfig
autohome-crawl	Upload error log	2026-07-05T17:32:39.8995534Z   Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Upload error log	2026-07-05T17:32:39.8996229Z   Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Upload error log	2026-07-05T17:32:39.8996775Z   Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.13/x64
autohome-crawl	Upload error log	2026-07-05T17:32:39.8997187Z   LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.13/x64/lib
autohome-crawl	Upload error log	2026-07-05T17:32:39.8997525Z   PYTHONUNBUFFERED: 1
autohome-crawl	Upload error log	2026-07-05T17:32:39.8997987Z   MINIMAX_API_KEY: *** secrets.MINIMAX_API_KEY }}
autohome-crawl	Upload error log	2026-07-05T17:32:39.8998363Z   ZEN_API_KEY: *** secrets.ZEN_API_KEY }}
autohome-crawl	Upload error log	2026-07-05T17:32:39.8998665Z   XAI_API_KEY: *** secrets.XAI_API_KEY }}
autohome-crawl	Upload error log	2026-07-05T17:32:39.8998986Z   OPENROUTER_API_KEY: *** secrets.OPENROUTER_API_KEY }}
autohome-crawl	Upload error log	2026-07-05T17:32:39.8999474Z   ACTION_PAT: ***
autohome-crawl	Upload error log	2026-07-05T17:32:39.8999706Z   HTTP_PROXY: 
autohome-crawl	Upload error log	2026-07-05T17:32:39.8999914Z   HTTPS_PROXY: 
autohome-crawl	Upload error log	2026-07-05T17:32:39.9000113Z   ALL_PROXY: 
autohome-crawl	Upload error log	2026-07-05T17:32:39.9000304Z   http_proxy: 
autohome-crawl	Upload error log	2026-07-05T17:32:39.9000491Z   https_proxy: 
autohome-crawl	Upload error log	2026-07-05T17:32:39.9000687Z   all_proxy: 
autohome-crawl	Upload error log	2026-07-05T17:32:39.9000884Z ##[endgroup]
autohome-crawl	Upload error log	2026-07-05T17:32:40.0653100Z (node:2367) [DEP0040] DeprecationWarning: The `punycode` module is deprecated. Please use a userland alternative instead.
autohome-crawl	Upload error log	2026-07-05T17:32:40.0654591Z (Use `node --trace-deprecation ...` to show where the warning was created)
autohome-crawl	Upload error log	2026-07-05T17:32:40.0696766Z Multiple search paths detected. Calculating the least common ancestor of all paths
autohome-crawl	Upload error log	2026-07-05T17:32:40.0700472Z The least common ancestor is /home/runner/work/crawl_cars/crawl_cars. This will be the root directory of the artifact
autohome-crawl	Upload error log	2026-07-05T17:32:40.0701758Z No files were found with the provided path: step1_error.log
autohome-crawl	Upload error log	2026-07-05T17:32:40.0702783Z remaining_error.log. No artifacts will be uploaded.
autohome-crawl	Post Run actions/checkout@main	﻿2026-07-05T17:32:40.0980135Z Post job cleanup.
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.1855572Z [command]/usr/bin/git version
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.1901283Z git version 2.54.0
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.1971595Z Temporarily overriding HOME='/home/runner/work/_temp/7ffb32bc-566c-4ec5-a34e-98b27dda42df' before making global git config changes
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.1973293Z Adding repository directory to the temporary git global config as a safe directory
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.1979738Z [command]/usr/bin/git config --global --add safe.directory /home/runner/work/crawl_cars/crawl_cars
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2019322Z Removing SSH command configuration
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2026646Z [command]/usr/bin/git config --local --name-only --get-regexp core\.sshCommand
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2068454Z [command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'core\.sshCommand' && git config --local --unset-all 'core.sshCommand' || :"
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2328279Z Removing HTTP extra header
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2336489Z [command]/usr/bin/git config --local --name-only --get-regexp http\.https\:\/\/github\.com\/\.extraheader
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2380630Z [command]/usr/bin/git submodule foreach --recursive sh -c "git config --local --name-only --get-regexp 'http\.https\:\/\/github\.com\/\.extraheader' && git config --local --unset-all 'http.https://github.com/.extraheader' || :"
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2643692Z Removing includeIf entries pointing to credentials config files
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2651406Z [command]/usr/bin/git config --local --name-only --get-regexp ^includeIf\.gitdir:
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2710369Z includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git.path
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2711371Z includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git/worktrees/*.path
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2712339Z includeif.gitdir:/github/workspace/.git.path
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2712970Z includeif.gitdir:/github/workspace/.git/worktrees/*.path
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2714529Z [command]/usr/bin/git config --local --get-all includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git.path
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2750766Z /home/runner/work/_temp/git-credentials-e3f777f1-ebe8-4f6c-8fd5-cb2cd3517f45.config
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2765065Z [command]/usr/bin/git config --local --unset includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git.path /home/runner/work/_temp/git-credentials-e3f777f1-ebe8-4f6c-8fd5-cb2cd3517f45.config
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2808963Z [command]/usr/bin/git config --local --get-all includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git/worktrees/*.path
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2840056Z /home/runner/work/_temp/git-credentials-e3f777f1-ebe8-4f6c-8fd5-cb2cd3517f45.config
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2861759Z [command]/usr/bin/git config --local --unset includeif.gitdir:/home/runner/work/crawl_cars/crawl_cars/.git/worktrees/*.path /home/runner/work/_temp/git-credentials-e3f777f1-ebe8-4f6c-8fd5-cb2cd3517f45.config
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2902605Z [command]/usr/bin/git config --local --get-all includeif.gitdir:/github/workspace/.git.path
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2929238Z /github/runner_temp/git-credentials-e3f777f1-ebe8-4f6c-8fd5-cb2cd3517f45.config
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2938013Z [command]/usr/bin/git config --local --unset includeif.gitdir:/github/workspace/.git.path /github/runner_temp/git-credentials-e3f777f1-ebe8-4f6c-8fd5-cb2cd3517f45.config
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2973881Z [command]/usr/bin/git config --local --get-all includeif.gitdir:/github/workspace/.git/worktrees/*.path
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.2999954Z /github/runner_temp/git-credentials-e3f777f1-ebe8-4f6c-8fd5-cb2cd3517f45.config
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.3008945Z [command]/usr/bin/git config --local --unset includeif.gitdir:/github/workspace/.git/worktrees/*.path /github/runner_temp/git-credentials-e3f777f1-ebe8-4f6c-8fd5-cb2cd3517f45.config
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.3046521Z [command]/usr/bin/git submodule foreach --recursive git config --local --show-origin --name-only --get-regexp remote.origin.url
autohome-crawl	Post Run actions/checkout@main	2026-07-05T17:32:40.3274547Z Removing credentials config '/home/runner/work/_temp/git-credentials-e3f777f1-ebe8-4f6c-8fd5-cb2cd3517f45.config'
autohome-crawl	Complete job	﻿2026-07-05T17:32:40.3411841Z Cleaning up orphan processes
autohome-crawl	Complete job	2026-07-05T17:32:40.3739667Z ##[warning]Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24: actions/upload-artifact@v4. For more information see: https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/

```
