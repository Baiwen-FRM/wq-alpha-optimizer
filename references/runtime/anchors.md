## Canonical numeric anchors

**Type: Canonical candidate source.** 只有本文件维护 generic numeric anchors。其它 reference 只解释何时需要某类尺度；非锚点值只有在当前 Alpha 已有相邻证据、明确经济/统计理由或可追溯 case-only evidence 时才允许局部细化。

### Time windows

| Anchor | Interpretation |
|---:|---|
| 5 | short weekly scale |
| 10 | short/bi-weekly scale |
| 20 | monthly scale |
| 60 | quarterly-scale signal |
| 120 | medium horizon |
| 250 | annual horizon |

选择 window 必须由 signal horizon、field refresh、persistence 或 event cycle 给出理由；不要把整表当网格。

### Decay

| Anchor | Use |
|---:|---|
| 0 | no smoothing / fast event signal |
| 3 | light smoothing |
| 5 | regular smoothing |
| 10 | medium smoothing |
| 15 | strong smoothing |

### Winsorize std

| Anchor | Use |
|---:|---|
| 2 | aggressive tail compression |
| 3 | regular tail control |
| 4 | mild tail control |
| 5 | very mild tail control |

### Simulation truncation

| Anchor | Use |
|---:|---|
| 0.05 | tighter weight cap |
| 0.08 | regular candidate |
| 0.10 | medium |
| 0.15 | looser cap |

Truncation 是 simulation weight handling，不等同 expression-level winsorization。

### Use rules

1. Generic setting 只有当前 Primary mechanism 明确指向该 setting 时才成为 candidate；不要为了“找更好参数”无条件调参。
2. 第一波只选少量机制上不同的自然尺度，不 dense-scan 相邻整数。
3. 孤立 winner = fragile evidence；需要机制解释或有限 confirmation 后才可 promotion。
4. 单次成功的非锚点不升级成全局 anchor。
5. `delay / region / universe` 不是 generic anchor；在本 optimizer 的 ordinary candidate 中属于 locked scope。
