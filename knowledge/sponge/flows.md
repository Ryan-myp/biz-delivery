# 核心流程

## 启动流程

### `sponge/cmd/sponge/main.go`
```
sponge/cmd/sponge/main.go
  ↓
  rootCMD, fmt, commands, os, generate
```

### `sponge/cmd/protoc-gen-json-field/main.go`
```
sponge/cmd/protoc-gen-json-field/main.go
  ↓
  flag, fmt, os, options, generate
```

### `sponge/cmd/serverNameExample_httpExample/main.go`
```
sponge/cmd/serverNameExample_httpExample/main.go
  ↓
  initial, app, a
```

### `sponge/cmd/serverNameExample_mixExample/main.go`
```
sponge/cmd/serverNameExample_mixExample/main.go
  ↓
  initial, app, a
```

### `sponge/cmd/protoc-gen-go-gin/main.go`
```
sponge/cmd/protoc-gen-go-gin/main.go
  ↓
  flag, os, fmt, time, router
```

### `sponge/cmd/serverNameExample_grpcGwPbExample/main.go`
```
sponge/cmd/serverNameExample_grpcGwPbExample/main.go
  ↓
  initial, app, a
```

### `sponge/cmd/serverNameExample_grpcHttpPbExample/main.go`
```
sponge/cmd/serverNameExample_grpcHttpPbExample/main.go
  ↓
  initial, app, a
```

### `sponge/cmd/serverNameExample_grpcPbExample/main.go`
```
sponge/cmd/serverNameExample_grpcPbExample/main.go
  ↓
  initial, app, a
```

### `sponge/cmd/serverNameExample_httpPbExample/main.go`
```
sponge/cmd/serverNameExample_httpPbExample/main.go
  ↓
  initial, app, a
```

### `sponge/cmd/serverNameExample_grpcExample/main.go`
```
sponge/cmd/serverNameExample_grpcExample/main.go
  ↓
  initial, app, a
```

### `sponge/cmd/protoc-gen-go-rpc-tmpl/main.go`
```
sponge/cmd/protoc-gen-go-rpc-tmpl/main.go
  ↓
  flag, os, fmt, time, service
```
