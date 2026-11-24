# 默认参数（`name = expression`）支持解题指导

### 问题本质

Anko 的语法只接受 `func f(a, b, c...)` 这种“纯标识符”形参列表，`parser/parser.go.y` 中对应的规则是 `FUNC '(' expr_idents [VARARG] ')'`；一旦写成 `func f(a, b = 1)`，lexer 会在 `=` 处报语法错误。同时 VM 的 `funcExpr` / `makeCallArgs` 只按 `FuncExpr.Params` 的个数（或最后一个可变参）绑定实参，完全没有“缺省值”的概念。

参考修复没有改语法文件，而是在解析入口增加一次**源码改写**：把带默认值的函数头改写成普通的可变参函数 `func f(__anko_default_args_N...)`，并在函数体最前面插入一段 prologue，在每次调用时检查实参个数、按顺序声明/绑定形参、在实参缺失时求值默认表达式。这样既不需要 goyacc，也不需要改 AST 和 VM。

### 关键文件与位置

#### 1. `parser/default_args.go`（新增文件，核心实现）

这个文件承担全部“识别默认参数、校验声明、生成改写后源码”的逻辑，必须放在 `package parser` 中，因为要用到 `lexer.go` 里的 `isLetter` / `isDigit` 和 `Error` 类型。

需要实现的类型和函数（建议与参考实现保持同名同签名，便于同包测试直接调用）：

- `type defaultArgumentParam struct { Name string; Default string; IsVariadic bool }`
  - 描述一个形参：名字、默认表达式源码（无默认为空字符串）、是否可变参。
- `rewriteDefaultArgumentFunctions(src string) (string, error)`
  - 顶层扫描器：遍历整个源码，跳过字符串和注释，发现 `func` 关键字后调用 `rewriteFunctionAt`，并维护一个递增计数器用于生成唯一的内部参数名。
- `rewriteFunctionAt(runes []rune, start int, counter int) (string, int, bool, error)`
  - 处理单个函数：定位形参括号、判断是否存在顶层 `=`、解析形参、定位函数体 `{`、生成替换文本。返回值 `next` 是函数体 `{` 之后的下标，`changed` 表示是否真的改写了（用于递增计数器）。
- `parseDefaultArgumentParams(src string) ([]defaultArgumentParam, bool, error)`
  - 按顶层逗号切分形参并逐项校验，返回形参列表和 `hasDefaults`。
- `parseDefaultArgumentParam(src string) (defaultArgumentParam, error)`
  - 解析单个形参：识别末尾 `...`、定位顶层 `=`、切出名字和默认表达式并做合法性校验。
- `buildDefaultArgumentPrologue(params []defaultArgumentParam, argsName string) string`
  - 生成插入函数体开头的 prologue 源码：参数个数检查、局部变量声明、实参绑定、默认值求值。
- 扫描/切分辅助函数：
  - `splitTopLevelArguments(runes []rune, separator rune) ([]string, error)`
  - `findTopLevelRune(runes []rune, target rune) (int, bool, error)`
  - `scanBalancedRunes(runes []rune, start int, open rune, close rune) (int, error)`
  - `scanQuotedRunes(runes []rune, start int) (int, error)`
  - `hasKeywordAt(runes []rune, index int, keyword string) bool`
  - `isValidIdentifier(name string) bool`
  - `newDefaultArgumentError(runes []rune, index int, message string) error`

#### 2. `parser/lexer.go`

- `func Parse(s *Scanner) (ast.Stmt, error)`，当前在第 589 行。
  - 这是所有解析路径（`ParseSrc`、`core.load`、外部直接调用 `Parse`）的公共入口。修复在这里先对 `s.src` 做源码改写，再用改写后的源码构造一个新的 `Scanner`，最后交给 `Lexer` / `yyParse`。
- `func ParseSrc(src string) (ast.Stmt, error)`，当前在第 608 行。
  - 不需要改；它内部调用 `Parse`，因此自动获得默认参数能力。
- `type Error struct`（第 23 行）和 `type Scanner struct`（第 36 行）。
  - `newDefaultArgumentError` 要返回 `*parser.Error`，并把 `Message` 设为 `invalid default argument declaration`、`Fatal` 设为 `true`。

#### 3. `core/core.go`

- `func Import(e *env.Env) *env.Env` 中的 `load` 内建函数，当前在第 76–90 行。
  - 现在手工 `new(parser.Scanner)` + `scanner.Init(...)` + `parser.Parse(scanner)`；参考实现改为直接调用 `parser.ParseSrc(string(body))`。
  - 这个改动本身不是功能必需（因为 `Parse` 已经统一改写），但它让 `load` 走同一条解析入口，避免以后再加预处理时漏掉 `load`；同时保留原有的 `*parser.Error` 处理（设置 `Filename` 后 panic）。

#### 4. 不需要修改但必须理解的文件

- `parser/parser.go.y`、`parser/parser.go`、`parser/Makefile`
  - `parser.go` 是 goyacc 生成并签入仓库的产物，`parser/Makefile` 调用 `goyacc` 重新生成。当前环境没有 `goyacc`（`which goyacc` 失败），所以**不能**靠修改 `.y` 再生成来支持新语法；只改 `.y` 不会影响实际编译使用的 `parser.go`。手改生成的 `parser.go` 也很脆弱。因此选择在 `Parse` 前做源码改写。
- `vm/vmExprFunction.go`
  - `funcExpr`（第 13 行）根据 `FuncExpr.Params` 和 `FuncExpr.VarArg` 构造 reflect 函数；`makeCallArgs`（第 212 行）负责实参绑定。
  - 改写后的函数只有一个可变参 `__anko_default_args_N`，VM 会把所有实参收集成 `[]interface{}` 绑定给它。这是 prologue 能拿到全部实参的基础，不需要改 VM。
- `ast/expr.go` 的 `FuncExpr`（第 133 行）
  - 不需要增加默认值字段；改写后仍是普通的 `Params []string` + `VarArg bool`。
- `vm/vmStmt.go` 的 `ThrowStmt`（第 598 行）
  - prologue 用 `throw` 产生参数个数错误；其错误消息会原样保留到 `err.Error()`。

### 解题思路

#### 为什么用源码改写

- 语法文件不能直接生效：`parser.go` 是签入的生成产物，环境里没有 goyacc，题目也明确要求不依赖外部 parser generator。
- 改 AST/VM 也不够：lexer/parser 仍然无法接受形参列表里的 `=`，必须先在源码层把非法语法变成合法语法。
- 源码改写可以完全复用现有的 lexer、parser、AST 和 VM：改写后的函数就是普通的可变参函数，现有机制天然支持。

#### 改写后的代码形态

把：

```anko
func f(a, b = a + 1, c...) {
    <原函数体>
}
```

改写成类似：

```anko
func f(__anko_default_args_0...) {
    if len(__anko_default_args_0) > 2 { throw "function wants 2 arguments but received " + toString(len(__anko_default_args_0)) };
    if len(__anko_default_args_0) < 1 { throw "function wants at least 1 arguments but received " + toString(len(__anko_default_args_0)) };
    var a = nil; a = __anko_default_args_0[0];
    var b = nil; if len(__anko_default_args_0) > 1 { b = __anko_default_args_0[1] } else { b = a + 1 };
    var c = []; if len(__anko_default_args_0) > 2 { c = __anko_default_args_0[2:] };
    <原函数体>
}
```

要点：

- 原来的形参列表整体替换成一个内部可变参名 `__anko_default_args_<counter>`；`func` 关键字、函数名、`{` 之前和之后的空白尽量保持原样。
- prologue 直接插在 `{` 之后，不引入额外换行（参考实现如此）。
- 因为改写后的函数是可变参函数，VM 会把调用实参收集成 `[]interface{}` 绑定给内部参数；prologue 再从这个切片里按位置取值。
- 默认表达式原样插入 prologue，所以它在**每次调用时**、在函数自己的新 env 中、按形参顺序求值；后面的默认值可以引用前面已经绑定的形参，也可以引用外层可见变量。
- 没有默认值的函数（形参列表里没有顶层 `=`）必须原样返回，不能做任何校验或重排，否则会破坏现有语法错误和 VM 行为。

#### 运行时数据流

1. 源码字符串进入 `parser.Parse`（直接调用或经 `ParseSrc` / `core.load`）。
2. `rewriteDefaultArgumentFunctions` 产出改写后的源码。
3. 用改写后的源码新建 `Scanner`，走原来的 lexer / goyacc / AST 流程。
4. AST 中该函数只有一个可变参 `__anko_default_args_N`。
5. 调用时 `vm.funcExpr` 把实参切片绑定给这个参数，然后执行函数体。
6. 函数体第一条就是 prologue：
   - 先做参数个数上/下界检查；
   - 再按形参顺序 `var` 声明局部变量；
   - 有实参就取 `args[i]`，没有就求值默认表达式；
   - 最后执行原函数体。
7. 默认表达式在函数 env 中求值，env 的 parent 是函数定义时的 env，因此能访问“可见变量”；前面已经 `var` 声明的形参也在当前 env 中，因此后面的默认值能引用它们。

#### 声明校验规则

只在形参列表存在顶层 `=` 时才进入校验；校验规则：

- 形参名必须是合法标识符（首字符 `isLetter`，其余 `isLetter` / `isDigit`；`_` 算 letter）。
- `name =` 后面必须有非空表达式。
- 可变参必须是最后一个形参。
- 可变参不能有默认值。
- 一个带默认值的固定形参后面，不能再出现不带默认值的固定形参。
- 可变参可以跟在带默认值的固定形参后面。

所有非法声明都返回 `*parser.Error`，`Message` 必须是 `invalid default argument declaration`，`Fatal` 为 `true`，位置由出错处的 rune 下标换算成行列。

### 解题步骤

#### 步骤 1：新建 `parser/default_args.go` 和数据模型

在 `parser` 包下新建文件，导入 `fmt`、`strings`、`unicode` 和 `github.com/mattn/anko/ast`。先定义 `defaultArgumentParam`，字段为 `Name`、`Default`、`IsVariadic`。

注意：不要在这个文件里重复实现 `isLetter` / `isDigit`，直接用 `lexer.go` 里已有的函数即可（同包）。

#### 步骤 2：实现“不被字符串/注释干扰”的扫描辅助函数

这些函数是后面所有解析的基础，必须先做对：

- `scanQuotedRunes(runes, start)`：
  - `start` 是引号位置；根据引号类型 `"`、`'`、`` ` `` 找到闭合引号，返回闭合引号后一位的下标。
  - 对 `"` 和 `'` 要处理反斜杠转义（跳过 `\` 和它后面的一个 rune）；对反引号原始字符串不处理转义。
  - 到 EOF 还没闭合则返回 `newDefaultArgumentError(..., "invalid default argument declaration")`。
- `scanBalancedRunes(runes, start, open, close)`：
  - 从 `start`（指向 `open`）开始做深度计数，跳过字符串和 `#` 行注释，返回匹配的 `close` 下标。
  - 用于找到形参列表的右括号。
- `findTopLevelRune(runes, target)`：
  - 维护 `()`、`[]`、`{}` 三种深度，跳过字符串和 `#` 注释；只在三种深度都为 0 时匹配 `target`，返回第一个匹配位置。
  - 用于在形参列表里找顶层 `=`，以及在默认表达式里避免把 `==`、括号内的 `=` 误当分隔符。
- `splitTopLevelArguments(runes, separator)`：
  - 同样的深度/字符串/注释处理，在顶层 `separator`（形参列表用 `,`）处切分，保留空片段（后面校验需要）。
- `hasKeywordAt(runes, index, keyword)`：
  - 精确匹配关键字，并检查前后字符不能是 letter/digit（`_` 也算 letter），避免把 `myfunc`、`func2`、`func_` 当成关键字。
- `isValidIdentifier(name)`：
  - 非空，首字符 `isLetter`，其余 `isLetter` 或 `isDigit`。
- `newDefaultArgumentError(runes, index, message)`：
  - 从 rune 下标计算 `Line` / `Column`（`\n` 换行，列从 1 开始），返回 `&Error{Message: message, Pos: ast.Position{...}, Fatal: true}`。

实现时建议把“跳过字符串/注释”的逻辑抽成小 helper，避免 `splitTopLevelArguments`、`findTopLevelRune`、`scanBalancedRunes` 三处行为不一致。

#### 步骤 3：解析并校验单个/多个形参

- `parseDefaultArgumentParam(src)`：
  1. `TrimSpace`。
  2. 如果以 `...` 结尾，标记 `IsVariadic = true`，去掉 `...` 再 `TrimSpace`。
  3. 用 `findTopLevelRune` 找第一个顶层 `=`。
  4. 有 `=`：`Name = TrimSpace(左边)`，`Default = TrimSpace(右边)`；无 `=`：`Name = TrimSpace(整个)`。
  5. 校验：`isValidIdentifier(Name)`；如果有 `=`，`Default` 不能为空。
  6. 返回 `defaultArgumentParam`。
- `parseDefaultArgumentParams(src)`：
  1. `splitTopLevelArguments` 按 `,` 切分。
  2. 特殊处理：如果只有一个片段且 `TrimSpace` 后为空，说明是 `func()`，返回空列表、`hasDefaults=false`、`nil`。
  3. 逐项调用 `parseDefaultArgumentParam`。
  4. 校验顺序（建议按参考实现）：
     - 可变参不是最后一个 → 非法；
     - 该项有默认值 → 记录 `hasDefaults` 和 `seenDefault`；
     - 该项无默认值且不是可变参且之前出现过默认值 → 非法（“带默认值的固定形参后面不能跟无默认值的固定形参”）；
     - 可变参且有默认值 → 非法。
  5. 任何非法情况都返回 `invalid default argument declaration` 错误。
  6. 返回 `params, hasDefaults, nil`。

注意：`splitTopLevelArguments` 会把空片段也返回；`func(,a)` 这种没有顶层 `=` 的畸形写法不应该进入这里（见步骤 5 的“没有 `=` 就原样返回”），所以不会改变它原来的 `syntax error: unexpected ','`。

#### 步骤 4：生成 prologue

`buildDefaultArgumentPrologue(params, argsName)` 的输出是一个字符串，直接拼在函数体 `{` 后面。生成逻辑：

1. 计算 `required` 和 `variadicIndex`：
   - 从前往后遍历，遇到可变参就记录 `variadicIndex` 并停止；
   - 在可变参之前，没有默认值的固定形参计入 `required`。
2. 如果没有可变参：
   - 生成上界检查：`if len(args) > len(params) { throw "function wants <N> arguments but received " + <参数个数转字符串> };`
   - `N` 是 `len(params)`，消息必须是 `function wants N arguments but received M`。
3. 如果 `required > 0`：
   - 生成下界检查：`if len(args) < required { throw "function wants at least <R> arguments but received " + <参数个数转字符串> };`
   - 注意消息里是 `at least`，和上界消息不同。
4. 按形参顺序逐个生成绑定语句：
   - 可变参：`var name = []; if len(args) > index { name = args[index:] };`
   - 无默认值的固定形参：`var name = nil; name = args[index];`
     - 因为 `required` 下界检查保证这些下标一定存在，所以可以安全直接取。
   - 有默认值的固定形参：`var name = nil; if len(args) > index { name = args[index] } else { name = <Default> };`
     - 默认表达式必须原样插入，不能提前求值或缓存。
5. 语句之间用 `;` 分隔；返回值末尾留一个空格，方便和原函数体拼接。

两个重要细节：

- **用 `var` 声明局部变量**：Anko 的普通赋值 `name = ...` 会通过 `SetValue` 向上查找已存在的同名变量，可能改写外层变量；`var name = nil` 先在当前函数 env 中建立局部绑定，才能保证形参是局部的，且后面的默认表达式能正确看到前面绑定的形参。
- **错误消息不要依赖 core 的 `toString`**：参考实现写的是 `toString(len(args))`，但 `toString` 是 `core.Import` 定义的，裸 `vm` 测试环境里没有它；如果隐藏测试直接用 `vm.Execute` + `env.NewEnv()` 测参数个数错误，会得到 `undefined symbol 'toString'` 而不是期望的 `function wants ...`。更稳的写法是 `"..." + len(args)`，Anko 的字符串拼接会自动把整数转成字符串，消息完全一致。

#### 步骤 5：改写单个函数头

`rewriteFunctionAt(runes, start, counter)` 的流程：

1. `index = start + len("func")`，跳过空白，然后一直前进到第一个 `(`。
   - 这样同时支持匿名函数 `func(...)` 和命名函数 `func name(...)`。
   - 如果到 EOF 都没找到 `(`，返回 `invalid default argument declaration`。
2. 用 `scanBalancedRunes(runes, index, '(', ')')` 找到形参列表的右括号 `paramEnd`。
3. 用 `findTopLevelRune(runes[index+1:paramEnd], '=')` 判断形参列表里有没有顶层 `=`：
   - **没有 `=`**：这是一个普通函数，不需要改写。但仍然要找到函数体 `{`（跳过空白），以便返回正确的 `next` 让外层继续扫描函数体里的嵌套函数。找到后返回 `string(runes[start:bodyStart+1])`、`bodyStart+1`、`false`、`nil`。如果找不到 `{`，参考实现返回 `invalid default argument declaration`。
   - **有 `=`**：调用 `parseDefaultArgumentParams` 解析并校验。解析失败时用 `newDefaultArgumentError(runes, start, err.Error())` 包装成 `*parser.Error`。
4. 找到函数体 `{`（`paramEnd` 之后跳过空白）；找不到则报 `invalid default argument declaration`。
5. 如果 `hasDefaults` 为 false（防御性分支，正常情况下有顶层 `=` 就一定有默认值），原样返回。
6. 生成替换文本：
   - `prefix = string(runes[start:index])`：从 `func` 到 `(` 之前的原文，保留函数名和空白。
   - `suffix = string(runes[paramEnd+1 : bodyStart+1])`：从 `)` 之后到 `{`（含 `{`）的原文，保留空白和 `{`。
   - `internalName = fmt.Sprintf("__anko_default_args_%d", counter)`。
   - 替换文本 = `prefix + "(" + internalName + "...)" + suffix + buildDefaultArgumentPrologue(params, internalName)`。
7. 返回替换文本、`bodyStart+1`、`true`、`nil`。

关键点：

- **没有顶层 `=` 时不要解析/校验形参**。这样 `func(,a){}` 仍然由 goyacc 报原来的 `syntax error: unexpected ','`，现有测试不会被破坏。
- `next` 必须指向函数体 `{` 之后，这样外层扫描器会继续扫描函数体，嵌套函数也能被改写。
- `counter` 只在 `changed == true` 时递增，保证每个被改写的函数有唯一内部参数名。

#### 步骤 6：实现顶层扫描器

`rewriteDefaultArgumentFunctions(src)`：

1. `runes := []rune(src)`，准备 `strings.Builder` 和 `counter := 0`。
2. 用 `i` 遍历：
   - 遇到 `#`：一直复制到 `\n` 之前（行注释原样保留），`i` 跳到换行处。
   - 遇到 `"`、`'`、`` ` ``：调用 `scanQuotedRunes`，把整段字符串原样复制，`i` 跳到闭合引号之后。
   - 如果 `hasKeywordAt(runes, i, "func")`：调用 `rewriteFunctionAt`；如果 `changed` 则 `counter++`；把返回的文本写入 builder，`i = next`。
   - 其他情况：复制当前 rune，`i++`。
3. 返回 builder 字符串。

注意：参考实现只跳过了 `#` 行注释，没有跳过 `//` 和 `/* */` 注释；如果源码注释里出现 `func`，可能会被误处理（见“易错点”）。

#### 步骤 7：接入 `parser.Parse`

在 `parser/lexer.go` 的 `Parse` 开头：

1. 调用 `rewriteDefaultArgumentFunctions(string(s.src))`。
2. 如果返回错误，直接 `return nil, err`。
3. 用改写后的字符串构造新的 `Scanner`：`scanner := &Scanner{src: []rune(rewritten)}`。
4. 用新 scanner 构造 `Lexer`，继续原来的 `yyParse` 流程。

`ParseSrc` 不需要改，它内部调用 `Parse`，自动获得改写能力。

为什么放在 `Parse` 而不是只放在 `ParseSrc`：`Parse` 是底层公共入口，`core.load`、外部直接调用 `parser.Parse` 的代码都能覆盖；只改 `ParseSrc` 会漏掉手工构造 `Scanner` 的调用方。

#### 步骤 8：更新 `core/core.go` 的 `load`

把：

```go
scanner := new(parser.Scanner)
scanner.Init(string(body))
stmts, err := parser.Parse(scanner)
```

改为：

```go
stmts, err := parser.ParseSrc(string(body))
```

保留后面的错误处理逻辑：如果是 `*parser.Error`，设置 `pe.Filename = s` 后 panic；否则 panic 原错误。这个改动让 `load` 和 `ParseSrc` 走同一条路径，避免手工构造 Scanner 时遗漏解析预处理。

#### 步骤 9：验证

先编译和跑现有测试：

```bash
gofmt -w parser/default_args.go parser/lexer.go core/core.go
go build ./...
go test ./...
```

现有测试里特别要确认：

- `func(,a){}` 仍然报 `syntax error: unexpected ','`（不能被新校验拦截）。
- 所有普通函数、可变参函数、`...` 展开调用的测试仍然通过。
- `core/testdata/core_test.go` 的 `load` 测试仍然通过。

再手工验证默认参数行为（建议覆盖）：

1. 基本缺省：`func f(a, b = 2) { return a + b }; f(1)` → `3`。
2. 全部缺省：`func f(a = 1, b = 2) { return a + b }; f()` → `3`。
3. 部分提供：`f(5)` → `7`。
4. 默认值引用前面的形参：`func f(a, b = a + 1) { return b }; f(1)` → `2`。
5. 默认值引用外层变量且每次调用重新求值：`x = 1; func f(a = x) { return a }; f(); x = 2; f()` → `1`、`2`。
6. 默认值从左到右求值：`i = 0; func next() { i++; return i }; func f(a = next(), b = next()) { return [a, b] }; f()` → `[1, 2]`。
7. 提供实参时不求值默认表达式（可用副作用变量验证）。
8. 可变参跟在默认参数后：`func f(a = 1, b...) { return [a, b] }; f()` → `[1, []]`；`f(5, 6, 7)` → `[5, [6, 7]]`。
9. 非法声明：`func f(a = 1, b) {}`、`func f(a... = 1) {}`、`func f(a = ) {}` 都返回 `invalid default argument declaration`。
10. 参数个数错误：`func f(a = 1) { return a }; f(1, 2)` 报 `function wants 1 arguments but received 2`；`func f(a, b = 1) {}; f()` 报 `function wants at least 1 arguments but received 0`。
11. 嵌套函数：`func outer(a = 1) { func inner(b = a + 1) { return b }; return inner() }; outer()` → `2`。
12. 通过 `load` 加载含默认参数的文件。
13. 如果隐藏测试可能在裸 `vm` 环境跑，额外用 `vm.Execute(env.NewEnv(), nil, script)` 验证参数个数错误，确认没有依赖 `toString`。

最后从当前默认分支（这个 checkout 是 `master`，没有 `main`）新建分支，把新增文件和修改一起提交：

```bash
git checkout -b feature/default-arguments
git add parser/default_args.go parser/lexer.go core/core.go
git commit -m "Add support for default argument values"
```

### 易错点与注意事项

#### A. 解析与扫描

1. **不要试图改 `parser/parser.go.y` 再生成**：环境没有 `goyacc`，`parser.go` 是签入的生成产物；只改 `.y` 不会影响实际解析，手改 `parser.go` 又非常脆弱。源码改写是本题可行的路线。
2. **改写必须挂在 `Parse`**：只在 `ParseSrc` 里做会漏掉直接调用 `parser.Parse(scanner)` 的代码；`core.load` 也应改为 `ParseSrc`。
3. **字符串和注释必须跳过**：扫描 `func`、找 `=`、切 `,` 时，字符串里的 `func`、`=`、`,` 都不能误判。参考实现处理了 `"`、`'`、`` ` `` 和 `#` 注释；建议同时处理 `//` 和 `/* */`，否则 `// func`、`/* func */` 可能被误改写或误报错。
4. **关键字边界检查**：`func` 必须是独立单词，不能匹配 `myfunc`、`func2`、`func_`。
5. **只认第一个顶层 `=`**：默认表达式里可能有 `==`、`<=`、`>=`、括号内的赋值等；用深度跟踪 + 字符串/注释跳过，确保 `a = b == c` 的默认值是 `b == c`。
6. **没有顶层 `=` 就原样返回**：这是保持旧行为的关键。`func(,a){}` 这类畸形写法不能被新校验改成 `invalid default argument declaration`，否则现有测试会失败。
7. **`next` 要指向函数体 `{` 之后**：否则嵌套在函数体里的函数不会被扫描和改写。
8. **嵌套函数在默认表达式里的情况**：参考实现把默认表达式原样插入 prologue，不会递归改写默认表达式内部的 `func`；因此 `func f(a = func(x = 1){ return x }) {}` 这种“默认值里再定义带默认参数的函数”会解析失败。如果测试覆盖这种场景，需要在生成 prologue 前对默认表达式递归调用改写逻辑。
9. **`func` 和 `{` 之间有注释**：参考实现只跳过空白，`func f(a) # comment\n { ... }` 会被误判为找不到 `{` 并报 `invalid default argument declaration`。如果要保持旧行为，定位 `{` 时也要跳过 `#`、`//`、`/* */` 注释。
10. **形参列表里的注释**：`splitTopLevelArguments` / `findTopLevelRune` 会跳过注释来确定结构，但注释文本仍留在片段里；默认表达式里带 `#` 注释时，插入单行 prologue 可能把后面的语句注释掉。需要的话在解析前剥离注释，或在生成的 prologue 中保留换行。
11. **未闭合字符串**：顶层扫描器遇到未闭合引号会直接返回 `invalid default argument declaration`，而原 lexer 会报 `unexpected EOF`。如果不想改变这类无关错误，可以让扫描器在非函数上下文只做“安全复制”，把真正的语法错误留给 lexer。
12. **空形参列表**：`func()` / `func( )` 没有顶层 `=`，应原样返回；`parseDefaultArgumentParams` 中“只有一个空片段”要特殊处理成零形参，而不是报错。
13. **尾随逗号**：`func f(a = 1, )` 参考实现会报 `invalid default argument declaration`；没有默认值时尾随逗号仍交给原语法报错。保持这个区分即可。

#### B. 校验与错误

14. **错误类型和消息必须精确**：返回 `*parser.Error`，`Message` 为 `invalid default argument declaration`，`Fatal` 为 `true`。测试通常比较 `err.Error()`，不要用 `fmt.Errorf` 包一层导致消息变化。
15. **校验顺序**：先识别可变参，再检查“可变参必须是最后一个”“可变参不能有默认值”“默认值固定形参后不能跟无默认值固定形参”。顺序不影响最终消息，但不要漏掉任何一条。
16. **形参名合法性**：用 lexer 的 `isLetter` / `isDigit`，支持 Unicode 和下划线；注意关键字（如 `if`）虽然能通过 `isValidIdentifier`，但生成的 `var if = nil` 会在后续解析报 `syntax error`，如果想统一成默认参数错误，需要额外排除关键字。
17. **内部参数名冲突**：`__anko_default_args_N` 是保留前缀；如果用户形参正好叫这个名字，prologue 里的 `var` 会覆盖内部 args 切片，后续 `len(args)` 就错了。可以用更不可能冲突的前缀，或在解析时检测冲突并换名。

#### C. 生成代码与运行时语义

18. **必须用 `var` 声明形参**：Anko 的普通赋值会向上查找同名变量并可能改写外层变量；`var name = nil` 才能建立函数局部绑定。这一点对“形参名和外层变量同名”的场景很关键。
19. **默认表达式按形参顺序插入**：不要提前计算、不要缓存、不要打乱顺序。这样后面的默认值才能看到前面已绑定的形参，也满足“从左到右求值”。
20. **参数个数消息**：
    - 无默认值的普通函数仍由 VM 的 `makeCallArgs` 报 `function wants N arguments but received M`；
    - 改写后的函数由 prologue 报同样的上界消息；
    - 缺省参数的下界消息是 `function wants at least R arguments but received M`，不要写成和上界一样的格式。
21. **不要依赖 core 的 `toString`**：参考实现用 `toString(len(args))`，裸 `vm` 环境没有 `toString`，参数个数错误会变成 `undefined symbol 'toString'`。建议直接用 `"..." + len(args)`，VM 的字符串拼接会自动转换整数，消息完全一致，且在有无 `core.Import` 的环境都可用。
22. **prologue 的隐式返回值**：Anko 函数没有显式 `return` 时返回最后一条语句的值。如果原函数体为空，prologue 的最后一条语句（例如默认值赋值或 `if`）会成为函数返回值：`func f(a = 1) {}` 会返回 `1`，`func f(a = 1, b...) {}` 会返回 `false`。参考实现没有处理这一点；建议在 prologue 末尾追加一条无害的 `nil` 表达式语句（`nil;`），让空函数体返回 `nil`，不影响有函数体的情况。
23. **不要用 `return nil` 收尾**：那会直接结束函数，跳过原函数体。只能用表达式语句 `nil;`。
24. **参数个数检查要在默认值求值之前**：prologue 先做上/下界检查，再绑定形参/求默认值；这样参数个数非法时不会执行默认表达式的副作用。
25. **可变参切片**：可变参绑定用 `args[index:]`，不要包含前面的固定形参；条件用 `len(args) > index`，不要用 `>=`，否则 `len == index` 时会取到空切片（虽然结果类似，但语义上应保持“没有多余实参就保持 `[]`”）。
26. **缺省判断只能用实参个数**：判断某个形参是否缺省，必须用 `len(args) > index`；不能用 `args[index] == nil`、`if args[index]` 之类的真值判断。显式传入 `nil`、`false`、`0` 都是有效实参，必须原样绑定，不能触发默认值。`func f(a = 1) { return a }; f(nil)` 应该返回 `nil`，而不是 `1`。
26. **无默认值固定形参可以直接下标**：因为 `required` 下界检查保证这些位置一定有实参；但 `required` 的计算必须在第一个可变参处停止，不能把可变参后面的东西算进去。
27. **展开调用 `f([1, 2]...)`**：改写后的函数是可变参函数，调用方用 `...` 展开时走 `CallSlice`，prologue 收到的是展开后的实参切片，个数检查仍然正确；不要假设调用方一定逐个传参。
28. **`go f()`**：默认参数函数在 goroutine 中也能工作；goroutine 里的错误照常被忽略/上报，不需要特殊处理。
29. **函数类型变化**：带默认值的函数在 reflect 层是 `func(context.Context, ...interface{}) (reflect.Value, reflect.Value)`，和普通函数的签名不同；`typeOf(f)` 的结果会变化。一般测试不会检查这个，但要有心理准备。
30. **参数个数错误的位置**：prologue 里的 `throw` 位置是改写后源码中的位置，不是原始调用点；现有测试通常只比较 `err.Error()`，如果隐藏测试检查位置，需要额外处理。

#### D. 集成与兼容性

30. **`Parse` 会忽略传入 `Scanner` 的扫描状态**：它只用 `s.src` 重新构造 Scanner；因此调用方必须保证 `s.src` 已经通过 `Init` 或 `ParseSrc` 设置好。不要在扫描到一半的 Scanner 上调用 `Parse`。
31. **`ParseSrc` 保持不变**：它内部调用 `Parse`，不要重复改写，否则会改写两次（第二次可能把已经改写的 `func(__anko_default_args_0...)` 当成普通函数，虽然通常无害，但没必要）。
32. **`core.load` 的错误处理要保留**：`*parser.Error` 的 `Filename` 赋值和 panic 行为不能丢；否则 `load` 的错误信息会变化。
33. **新文件必须在 `package parser`**：这样才能直接使用 `isLetter`、`isDigit`、`Error`、`Scanner` 等未导出符号。
34. **gofmt**：新增文件后运行 `gofmt -w`，避免格式问题影响提交。

#### E. 测试与提交

35. **优先保证现有测试全绿**：`go test ./...` 必须通过，尤其是 `vm/vmFunctions_test.go` 里的普通函数、可变参函数、`func(,a)` 语法错误测试，以及 `core/testdata/core_test.go` 的 `load` 测试。
36. **补充默认参数测试**：至少覆盖基本缺省、部分提供、默认值引用前面形参、默认值引用外层变量、调用时重新求值、从左到右求值、可变参跟在默认参数后、四类非法声明、参数个数上/下界、嵌套函数、`load`。
37. **裸 vm 环境测试**：如果隐藏测试在 `vm` 包内用 `env.NewEnv()` 直接执行，务必确认参数个数错误不依赖 `toString`。
38. **提交前检查分支**：当前 checkout 是 detached HEAD，默认分支是 `master`（没有 `main`）；从当前默认分支新建分支后再提交，提交信息说明新增默认参数支持。