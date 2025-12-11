# 适配阿里云 CodeUp 仓库的 Git 操作指南（完整流程）
## 一、核心调整说明
原指南仅需替换仓库地址，**所有操作流程、分支规范、提交规范完全不变**，以下是适配阿里云 CodeUp 的完整步骤（含 SSH/HTTPS 两种地址用法）。

## 二、开始使用（替换仓库地址后直接用）
### 方式1：HTTPS 地址（无需配置密钥，输入账号密码即可）
```bash
# 1. 克隆项目（替换为阿里云 HTTPS 地址）
git clone https://codeup.aliyun.com/68bed740725067d38cf1717e/CloudSyncEdge.git
cd CloudSyncEdge

# 2. 创建你的分支（四选一，和原流程一致）
git checkout -b feature/a-ecu-core       # A: ECU库
git checkout -b feature/b-websocket      # B: WebSocket
git checkout -b feature/c-rest-api       # C: REST API
git checkout -b feature/d-jsonrpc        # D: 协议

# 3. 推送到远程（首次推送绑定分支，分支名和本地一致）
git push -u origin 你的分支名  # 例：git push -u origin feature/a-ecu-core
```

### 方式2：SSH 地址（需提前配置密钥，免密码登录，推荐）
#### 第一步：提前配置 SSH 密钥（仅需一次）看飞书文档
1. 本地生成 SSH 密钥（打开终端执行）：
   ```bash
   ssh-keygen -t rsa -C "你的邮箱地址"  # 例：ssh-keygen -t rsa -C "student@xxx.com"
   ```
   - 执行后按 3 次回车（默认保存路径、不设置密码），生成密钥文件（默认在 `~/.ssh/` 目录下）。
2. 复制公钥内容：
   - Windows：打开 `C:\Users\你的用户名\.ssh\id_rsa.pub`，复制全部内容。
   - Mac/Linux：执行 `cat ~/.ssh/id_rsa.pub`，复制输出的全部内容。
3. 配置到阿里云 CodeUp：
   - 登录阿里云 CodeUp 仓库页面 → 右上角「个人设置」→ 左侧「SSH 密钥」→「添加密钥」→ 粘贴公钥内容 → 保存。

#### 第二步：克隆和推送（用 SSH 地址）
```bash
# 1. 克隆项目（替换为阿里云 SSH 地址）
git clone git@codeup.aliyun.com:68bed740725067d38cf1717e/CloudSyncEdge.git
cd CloudSyncEdge

# 2. 创建分支（和原流程一致，四选一）
git checkout -b feature/a-ecu-core

# 3. 推送到远程（首次推送绑定分支）
git push -u origin feature/a-ecu-core
```

## 三、每日流程（完全不变，直接执行）
```bash
# 1. 获取 master 分支最新代码（拉取的是阿里云仓库的 master）
git checkout master
git pull origin master

# 2. 回到自己的分支，合并 master 最新代码（避免冲突）
git checkout 你的分支名  # 例：git checkout feature/a-ecu-core
git merge master

# 3. 开发后提交（提交规范不变）
git add .  # 暂存所有修改
git commit -m "类型(模块): 描述"  # 例：feat(ecu): 添加ECU初始化方法
git push  # 推送至阿里云对应分支
```

## 四、提交规范（完全不变）
| 角色 | 模块       | 示例                          |
|------|------------|-------------------------------|
| A    | ecu        | feat(ecu): 添加ECU类          |
| B    | southbound | fix(southbound): 修复WebSocket连接超时 |
| C    | northbound | feat(northbound): 添加查询API  |
| D    | protocol   | feat(protocol): 实现JSONRPC编码器 |

## 五、分支结构（完全不变）
```text
master（主分支，阿里云仓库的master）
├── feature/a-ecu-core      # A：ECU库开发分支
├── feature/b-websocket     # B：WebSocket开发分支
├── feature/c-rest-api      # C：REST API开发分支
└── feature/d-jsonrpc       # D：协议开发分支
```

## 六、解决冲突（完全不变）
1. 合并 master 时若出现冲突，终端会提示「Automatic merge failed」。
2. 打开冲突文件，找到冲突标记：
   ```
   <<<<<<< HEAD          # 你当前分支的代码
   你的代码内容
   =======
   从master合并过来的代码内容
   >>>>>>> master        # master分支的代码
   ```
3. 删除冲突标记（`<<<<<<<`、`=======`、`>>>>>>>`），保留正确的代码（可和团队协商）。
4. 重新提交：
   ```bash
   git add 冲突的文件名  # 例：git add src/ecu/ECU.cpp
   git commit -m "fix: 解决ECU类初始化方法冲突"
   git push
   ```

## 七、命令速查（完全不变）
```bash
git status          # 查看本地文件修改状态
git log --oneline   # 简洁查看提交历史（含哈希值）
git branch          # 查看所有分支（当前分支前有*）
git checkout 分支名 # 切换到指定分支（例：git checkout master）
git add 文件名      # 暂存单个文件（例：git add src/websocket.cpp）
git add .           # 暂存所有修改文件
git commit -m "描述" # 提交暂存区到本地仓库
git push           # 推送本地分支到阿里云远程仓库
git pull           # 拉取远程分支最新代码到本地
```

## 八、注意事项（完全不变）
✅ 要做：
- 每天开发前必须执行 `git pull origin master`（拉取阿里云 master 最新代码）
- 所有开发工作都在自己的 `feature/xxx` 分支进行
- 提交信息严格按照「类型(模块): 描述」格式写，清晰易懂

❌ 不要：
- 直接在 master 分支写代码或提交
- 提交空信息（`git commit -m ""` 会报错，也不允许）
- 遇到冲突警告时强行推送（必须先解决冲突）

## 九、紧急处理（完全不变）
```bash
# 1. 代码写乱了，想回退到最近一次提交（丢弃所有未提交修改）
git reset --hard HEAD

# 2. 误删了某个文件（未提交删除操作），恢复到最近一次提交的版本
git checkout -- 文件名  # 例：git checkout -- src/ecu/ECU.h

# 3. 在错的分支写了代码（还没提交），转移到正确分支
git stash  # 暂存当前分支的修改
git checkout 正确分支  # 例：git checkout feature/a-ecu-core
git stash pop  # 把暂存的修改恢复到正确分支

# 4. 若已提交到错的分支，可联系团队协助迁移（避免误操作）
```

## 十、关键提醒
1. 两种地址选择：
   - 新手推荐用 **HTTPS 地址**，无需配置密钥，克隆时输入阿里云 CodeUp 的「用户名」和「密码」即可（若开启了二次验证，密码需用「访问令牌」，在 CodeUp 个人设置 → 访问令牌 中创建）。
   - 频繁开发推荐用 **SSH 地址**，配置一次密钥后免密码登录，更高效。
2. 仓库地址验证：
   克隆后可执行 `git remote -v` 查看远程仓库地址是否正确，输出如下即正常：
   ```
   origin  git@codeup.aliyun.com:68bed740725067d38cf1717e/CloudSyncEdge.git (fetch)
   origin  git@codeup.aliyun.com:68bed740725067d38cf1717e/CloudSyncEdge.git (push)
   ```
3. 若之前克隆过原仓库，想切换到阿里云仓库：
   ```bash
   git remote set-url origin 阿里云地址  # 例：git remote set-url origin https://codeup.aliyun.com/68bed740725067d38cf1717e/CloudSyncEdge.git
   ```