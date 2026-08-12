# 代码库学习任务

你是一个资深软件架构师。请基于以下代码扫描结果，
总结这个系统的架构、业务流程、数据模型和关键技术决策。

## 仓库信息
- **creative-platform**: go @ /Users/yanping.ma/GolandProjects/creative-platform

## 代码结构摘要
- Structs: 800
- Functions: 1055
- Routes: 113
- Imports: 0

## 数据库表推断

### `cp_ad_share_sub_task_tab` (Entity: AdShareSubTaskEntity)
文件: creative-platform/dao/entity/ad_share_sub_task.go
- `SubTaskId`: int64 [PK] gorm:column:sub_task_id;PRIMARY_KEY json:sub_task_id
- `TaskId`: int64 gorm:column:task_id json:task_id
- `SubTaskTimestamp`: int64 gorm:column:sub_task_timestamp
- `SubTaskOperator`: string gorm:column:sub_task_operator
- `SubTaskOp`: int gorm:column:sub_task_op
- `PartnerId`: int64 gorm:column:partner_id json:partner_id
- `GroupDetails`: string gorm:column:group_details
- `ModuleResult`: string gorm:column:module_result
- `SubTaskStatus`: int gorm:column:sub_task_status

### `cp_ad_share_sub_task_tab` (Entity: AdShareSubTaskInfo)
文件: creative-platform/dao/entity/ad_share_sub_task.go

### `cp_ad_share_sub_task_module_tab` (Entity: AdShareSubTaskModuleEntity)
文件: creative-platform/dao/entity/ad_share_sub_task_module.go
- `ModuleId`: int64 [PK] gorm:column:module_id;PRIMARY_KEY json:module_id
- `SubTaskId`: int64 gorm:column:sub_task_id json:sub_task_id
- `TaskId`: int64 gorm:column:task_id json:task_id
- `PartnerId`: int64 gorm:column:partner_id json:partner_id
- `GroupId`: int64 gorm:column:group_id json:group_id
- `RelatedExternalDesc`: string gorm:column:related_external_desc
- `ModuleType`: int gorm:column:module_type
- `ModuleResult`: string gorm:column:module_result
- `ModuleStatus`: int gorm:column:module_status

### `cp_ad_group_tab` (Entity: AdGroupEntity)
文件: creative-platform/dao/entity/adgroup.go
- `GroupId`: int64 [PK] gorm:column:group_id;PRIMARY_KEY json:group_id
- `AdGroupId`: int64 gorm:column:ad_group_id
- `AdGroupSource`: int gorm:column:ad_group_source
- `OpStatus`: int gorm:column:op_status
- `AdGroupName`: string gorm:column:ad_group_name
- `Geo`: string gorm:column:geo
- `CreativeType`: int gorm:column:creative_type
- `AdStartTime`: int64 gorm:column:ad_start_time
- `AdEndTime`: int64 gorm:column:ad_end_time
- `CampaignPurpose`: int gorm:column:campaign_purpose
- `CampaignName`: string gorm:column:campaign_name
- `Messaging`: int gorm:column:messaging
- `ContentCategory`: string gorm:column:content_category
- `Version`: string gorm:column:version
- `AdShortenHeadline`: string gorm:column:ad_shorten_headline

### `cp_ad_group_tab` (Entity: AdGroupPartnerStatistic)
文件: creative-platform/dao/entity/adgroup.go
- `PartnerId`: int64 gorm:column:partner_id
- `GroupSubmittedCount`: int64 gorm:column:submitted_count
- `GroupPendingSharerCount`: int64 gorm:column:pending_share_count
- `GroupSharedCount`: int64 gorm:column:shared_count
- `GroupAddOnCount`: int64 gorm:column:add_on_count
- `GroupPendingRegularPausedCount`: int64 gorm:column:pending_regular_count
- `GroupPendingEmergencyPausedCount`: int64 gorm:column:pending_emergency_count

### `cp_ad_group_tab` (Entity: AdGroupWithAdShares)
文件: creative-platform/dao/entity/adgroup.go

### `cp_ad_group_partner_relation_tab` (Entity: AdGroupPartnerRelationEntity)
文件: creative-platform/dao/entity/adgroup_partner_relation.go
- `GroupPartnerRelationId`: int64 [PK] gorm:column:group_partner_relation_id;PRIMARY_KEY
- `PartnerId`: int64 gorm:column:partner_id
- `GroupId`: int64 gorm:column:group_id
- `ShareStatus`: int gorm:column:share_status
- `EmergencyPauseStatus`: int gorm:column:emergency_pause_status
- `AddOnStatus`: int gorm:column:add_on_status

### `cp_ad_group_partner_task_tab` (Entity: AdGroupPartnerTaskEntity)
文件: creative-platform/dao/entity/adgroup_partner_task.go
- `TaskId`: int64 [PK] gorm:column:task_id;PRIMARY_KEY
- `GroupDetail`: string gorm:column:group_detail
- `PartnerId`: int64 gorm:column:partner_id
- `RecordId`: int64 gorm:column:record_id
- `TaskType`: int gorm:column:task_type
- `TaskStatus`: int gorm:column:task_status

### `cp_admin_operation_log` (Entity: AdminOperationLogEntity)
文件: creative-platform/dao/entity/admin_operation_log.go
- `Id`: int64 [PK] gorm:column:id;PRIMARY_KEY
- `ToolName`: string gorm:column:tool_name
- `ToolTypeCode`: int gorm:column:tool_type_code
- `RequestParam`: string gorm:column:request_param
- `RequestPath`: string gorm:column:request_path
- `RequestSequence`: string gorm:column:request_sequence
- `ReportUrl`: string gorm:column:report_url
- `ReportExpireTime`: int64 gorm:column:report_expire_time
- `HttpMethod`: string gorm:column:http_method
- `OperateTime`: int64 gorm:column:operate_time
- `OperateUser`: string gorm:column:operate_user
- `OperationFinishTime`: int64 gorm:column:operation_finish_time
- `OperationStatus`: int gorm:column:operation_status
- `TotalAmount`: int64 gorm:column:total_amount
- `SuccessAmount`: int64 gorm:column:success_amount

### `cp_ad_share_record_tab` (Entity: AdShareRecordEntity)
文件: creative-platform/dao/entity/adshare_record.go
- `ShareRecordId`: int64 [PK] gorm:column:share_record_id;PRIMARY_KEY
- `ExternalTaskId`: int64 gorm:column:external_task_id
- `AdSource`: int gorm:column:ad_source
- `GroupId`: int64 gorm:column:group_id
- `PartnerId`: int64 gorm:column:partner_id
- `CreativeId`: int64 gorm:column:creative_id
- `AdDownloadUrl`: string gorm:column:ad_download_url
- `Creator`: string gorm:column:creator
- `CreateTime`: int64 gorm:column:create_time
- `Updater`: string gorm:column:updater
- `UpdateTime`: int64 gorm:column:update_time
- `ShareUser`: string gorm:column:share_user
- `ShareTime`: int64 gorm:column:share_time
- `ShareTaskId`: int64 gorm:column:share_task_id
- `ShareTaskType`: int gorm:column:share_task_type

### `cp_ad_share_record_tab` (Entity: AdShareRecordWithPartner)
文件: creative-platform/dao/entity/adshare_record.go

### `cp_ad_share_task_tab` (Entity: AdShareTask)
文件: creative-platform/dao/entity/adshare_task.go
- `TaskId`: int64 [PK] gorm:column:task_id;PRIMARY_KEY
- `TaskTimestamp`: int64 gorm:column:task_timestamp
- `TaskOperator`: string gorm:column:task_operator
- `TaskOp`: int gorm:column:task_op
- `TaskSendType`: int gorm:column:task_send_type
- `GroupList`: string gorm:column:group_list
- `SkipGroupList`: string gorm:column:skip_group_list
- `TaskStatus`: int gorm:column:task_status
- `TaskGroupTotal`: int64 gorm:column:task_group_total
- `TaskGroupSkip`: int64 gorm:column:task_group_skip
- `TaskGroupSuccess`: int64 gorm:column:task_group_success
- `TaskPartnerTotal`: int64 gorm:column:task_partner_total
- `TaskPartnerSkip`: int64 gorm:column:task_partner_skip
- `TaskPartnerSuccess`: int64 gorm:column:task_partner_success
- `Remark`: string gorm:column:remark

### `cp_ad_share_task_tab` (Entity: AdShareTaskGroupStatistic)
文件: creative-platform/dao/entity/adshare_task.go
- `GroupId`: int64 gorm:column:group_id
- `TaskInitCount`: int64 gorm:column:init_count
- `TaskFailedCount`: int64 gorm:column:failed_count
- `TaskSuccessCount`: int64 gorm:column:success_count

### `cp_ad_share_task_tab` (Entity: AdShareTaskPartnerStatistic)
文件: creative-platform/dao/entity/adshare_task.go
- `PartnerId`: int64 gorm:column:partner_id
- `TaskInitCount`: int64 gorm:column:init_count
- `TaskFailedCount`: int64 gorm:column:failed_count
- `TaskSuccessCount`: int64 gorm:column:success_count

### `cp_ad_share_task_tab` (Entity: AdShareTaskGroupLevel)
文件: creative-platform/dao/entity/adshare_task.go

## 关键业务 Struct

### `AdGroupModule`
文件: creative-platform/app/adminapi/adgroup/adgroup_module.go

### `HelloRequest`
文件: creative-platform/app/adminapi/adgroup/adgroup_req.go
- `GEO`: string
- `Type`: string
- `Operation`: string

### `CreateAdGroupRequest`
文件: creative-platform/app/adminapi/adgroup/adgroup_req.go

### `EditAdGroupRequest`
文件: creative-platform/app/adminapi/adgroup/adgroup_req.go
- `AdGroup`: AdGroupInfo json:ad_group_info
- `DeleteCreatives`: []int64 json:delete_creatives
- `LockSequence`: string json:lock_sequence

### `DeleteAdGroupRequest`
文件: creative-platform/app/adminapi/adgroup/adgroup_req.go
- `GroupId`: int64

### `GetAdGroupDetailRequest`
文件: creative-platform/app/adminapi/adgroup/adgroup_req.go
- `GroupId`: int64

### `ListAdGroupsRequest`
文件: creative-platform/app/adminapi/adgroup/adgroup_req.go
- `Id`: int64
- `AdGroupName`: string
- `AdGroupId`: int64
- `ExternalTaskId`: int64
- `Geo`: string
- `Status`: int
- `CreativeType`: int
- `CampaignStartTime`: int64
- `CampaignEndTime`: int64
- `CampaignPurpose`: int

### `ListPartnersRequest`
文件: creative-platform/app/adminapi/adgroup/adgroup_req.go
- `PartnerId`: int64
- `PartnerName`: string
- `CampaignPurpose`: int
- `WithHidden`: int
- `Page`: int64
- `PageSize`: int64

### `GetAdGroupRequirementRequest`
文件: creative-platform/app/adminapi/adgroup/adgroup_req.go
- `Geo`: string
- `MediaType`: string
- `PartnerType`: int

### `LockAdGroupRequest`
文件: creative-platform/app/adminapi/adgroup/adgroup_req.go

### `UnLockAdGroupRequest`
文件: creative-platform/app/adminapi/adgroup/adgroup_req.go

### `ShareNewRequest`
文件: creative-platform/app/adminapi/adgroup/adgroup_req.go

### `ShareAddOnRequest`
文件: creative-platform/app/adminapi/adgroup/adgroup_req.go

### `ShareEmergentPauseRequest`
文件: creative-platform/app/adminapi/adgroup/adgroup_req.go
- `EmergencyEndTime`: int64 json:emergency_end_time
- `Geo`: string json:geo

### `AutoMailAdGroupRequest`
文件: creative-platform/app/adminapi/adgroup/adgroup_req.go
- `GroupIdList`: []int64 json:group_id_list

### `ListAdGroupSharePartnersRequest`
文件: creative-platform/app/adminapi/adgroup/adgroup_req.go
- `AdGroupId`: int64

### `ShareResendRequest`
文件: creative-platform/app/adminapi/adgroup/adgroup_req.go
- `GroupIdList`: []int64 json:group_id_list

### `HelloResponse`
文件: creative-platform/app/adminapi/adgroup/adgroup_rsp.go

### `CreateAdGroupResponse`
文件: creative-platform/app/adminapi/adgroup/adgroup_rsp.go
- `AdGroupName`: string json:ad_group_name
- `LockSequence`: string json:lock_sequence

### `EditAdGroupResponse`
文件: creative-platform/app/adminapi/adgroup/adgroup_rsp.go

## API 路由
- `Group /api/adgroup` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `POST /share/resend` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `GET /hello/:operation` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `POST /create` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `POST /:group_id/edit` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `GET /:group_id/detail` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `DELETE /:group_id/delete` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `GET /list` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `GET /partner/list` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `GET /requirement` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `POST /lock` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `POST /unlock` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `GET /:group_id/partners` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `POST /partner/updatestatus` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `POST /share/new` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `POST /share/add` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `POST /share/emergencypause` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
- `Group /api/auth` (creative-platform/app/adminapi/auth/auth_module.go)
- `Group /api/auth` (creative-platform/app/adminapi/auth/auth_module.go)
- `GET /login` (creative-platform/app/adminapi/auth/auth_module.go)
- `GET /permissions` (creative-platform/app/adminapi/auth/auth_module.go)
- `POST /logout` (creative-platform/app/adminapi/auth/auth_module.go)
- `GET /login_callback` (creative-platform/app/adminapi/auth/auth_module.go)
- `Group /api/cp` (creative-platform/app/adminapi/cpconfig/cpconfig_module.go)
- `POST configs/:module/save` (creative-platform/app/adminapi/cpconfig/cpconfig_module.go)
- `POST /configs` (creative-platform/app/adminapi/cpconfig/cpconfig_module.go)
- `POST /partner/save` (creative-platform/app/adminapi/cpconfig/cpconfig_module.go)
- `GET /partner/:partner_id/detail` (creative-platform/app/adminapi/cpconfig/cpconfig_module.go)
- `DELETE /partner/:partner_id/delete` (creative-platform/app/adminapi/cpconfig/cpconfig_module.go)
- `POST /requirement/PNS/creative/requirement/save` (creative-platform/app/adminapi/cpconfig/cpconfig_module.go)

## 服务层
- **AdminapiService** (0 methods)
- **DriveService** (0 methods)
- **AdShareServiceConfig** (0 methods)
- **MySqlManager** (0 methods)
- **AdminRedisService** (0 methods)
- **DriveRedisService** (0 methods)

## 关键源码片段

以下是从路由文件和入口点提取的核心实现代码，帮助理解业务逻辑：

### `CreateAdGroup` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
```go
func (m *AdGroupModule) CreateAdGroup(c *ginweb.Context, req *CreateAdGroupRequest) ginweb.Response {

	ctx := ginbase.NewContext(c)
	adGroupModel, err := req.RequestToModel(ctx)
	if err != nil {
		return resp.WithError(ctx, err)
	}

	err = util.VerifyAdGroupName(ctx, adGroupModel, "create")
	if err != nil {
		return resp.WithError(ctx, err)
	}

	adGroupEntity, err := adGroupModel.ToEntity(ctx)
	if err != nil {
		return resp.WithError(ctx, err)
	}
	currentTime := time.Now().Unix()
	adGroupEntity.Creator = c.User().Email
	adGroupEntity.CreateTime = currentTime
	adGroupEntity.Updater = c.User().Email
	adGroupEntity.UpdateTime = currentTime

	_, err = dao.CreateAdGroup(ctx, adGroupEntity)
	if err != nil {
		return resp.WithError(ctx, err)
	}

	userLockInfo := &model.UserLockInfo{
		UserEmail:    c.User().Email,
		LockSequence: "",
	}
	lockResp, webResponse := m.lockAdGroup(ctx, adGroupEntity.GroupId, userLockInfo)
	if lockResp == nil {
		return webResponse
	}

	rsp := &CreateAdGroupResponse{
		LockSequence: lockResp.LockSequence,
	}
	rsp.ConstructResp(ctx, adGroupEntity)

	return resp.WithSuccess(ctx, rsp)
}
```

### `DeleteAdGroup` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
```go
func (m *AdGroupModule) DeleteAdGroup(c *ginweb.Context, req *DeleteAdGroupRequest) ginweb.Response {
	ctx := ginbase.NewContext(c)
	adGroupEntity, err := util.VerifyAdGroup(ctx, req.GroupId)
	if err != nil {
		return resp.WithError(ctx, err)
	}

	group := &model.AdGroupModel{}
	group.FromEntity(ctx, adGroupEntity)
	rootOpStatus := group.GetRootOpStatus(ctx)
	if group.OpStatus == constant.AD_GROUP_OP_STATUS_PENDING_SHARE_CODE ||
		rootOpStatus == constant.AD_GROUP_OP_STATUS_SHARED_CODE {
		return resp.WithError(ctx, errors.AD_GROUP_SHARED)
	}

	rsp := &DeleteAdGroupResponse{
		IsLock: false,
	}
	userLockInfo, err := util.VerifyAdGroupIsLock(ctx, req.GroupId)
	if err != nil {
		if err == errors.SERVER_BUSY && userLockInfo != nil {
			rsp.IsLock = true
			rsp.UserEmail = userLockInfo.UserEmail
			return resp.Response(ctx, rsp, err)
		}
		return resp.Response(ctx, rsp, err)
	}

	adGroupEntity.Updater = c.User().Email
	adGroupEntity.UpdateTime = time.Now().Unix()
	err = dao.DeleteAdGroup(ctx, adGroupEntity)
	if err != nil {
		return resp.WithError(ctx, err)
	}

	return resp.WithSuccess(ctx, nil)
}
```

### `EditAdGroup` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
```go
func (m *AdGroupModule) EditAdGroup(c *ginweb.Context, req *EditAdGroupRequest) ginweb.Response {

	ctx := ginbase.NewContext(c)

	userLockInfo := &model.UserLockInfo{
		UserEmail:    c.User().Email,
		LockSequence: req.LockSequence,
	}
	adGroup, err := util.CompareAdGroupWithLock(ctx, *req.AdGroup.GroupId, userLockInfo)
	if err != nil {
		return resp.WithError(ctx, err)
	}
	currentGroupModel := &model.AdGroupModel{}
	currentGroupModel.FromEntity(ctx, adGroup)
	groupStatus := currentGroupModel.GetAdGroupStatus(ctx)
	if groupStatus == constant.AD_GROUP_STATUS_PAUSED_CODE ||
		currentGroupModel.OpStatus == constant.AD_GROUP_OP_STATUS_PENDING_SHARE_CODE ||
		currentGroupModel.OpStatus == constant.AD_GROUP_OP_STATUS_PENDING_REGULAR_PAUSED_CODE ||
		currentGroupModel.OpStatus == constant.AD_GROUP_OP_STATUS_PENDING_EMERGENCY_PAUSED_CODE {
		return resp.WithError(ctx, errors.AD_GROUP_CANNOT_EDIT)
	}

	adGroupModel, err := req.RequestToModel(ctx, adGroup)
	if err != nil {
		return resp.WithError(ctx, err)
	}

	isEndTimeEdit := util.CompareAdGroupEndTimeEdit(ctx, currentGroupModel, adGroupModel)

	err = util.VerifyAdGroupName(ctx, adGroupModel, "edit")
	if err != nil {
		return resp.WithError(ctx, err)
	}

	creatives := make([]*entity.CreativeEntity, 0, len(req.DeleteCreatives))
	if len(req.DeleteCreatives) != 0 {
		creativeCond := req.BuildQueryCreativesCondition(ctx, adGroupModel.GroupId)
		creatives, err = dao.QueryCreativesByCondition(ctx, creativeCond, nil, nil)
		if err != nil {
```

### `GetAdGroupDetail` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
```go
func (m *AdGroupModule) GetAdGroupDetail(c *ginweb.Context, req *GetAdGroupDetailRequest) ginweb.Response {
	ctx := ginbase.NewContext(c)
	adGroupEntity, err := util.VerifyAdGroup(ctx, req.GroupId)
	if err != nil {
		return resp.WithError(ctx, err)
	}
	adGroupModel, err := model.ConstructAdGroupModel(ctx, adGroupEntity)
	if err != nil {
		return resp.WithError(ctx, err)
	}

	cond := &condition.CreativeCondition{
		GroupId:      gormcore.Equal(adGroupModel.GroupId),
		CreativeTeam: gormcore.Equal(constant.CREATIVE_TEAM_CODE_OMPNS),
		Geo:          gormcore.Equal(adGroupModel.Geo),
		IsDeleted:    gormcore.Equal(constant.CREATIVE_IS_DELETED_FALSE),
	}
	creatives, err := dao.QueryCreativesByCondition(ctx, cond, nil, nil)
	if err != nil {
		return resp.WithError(ctx, err)
	}
	creativeIds := entity.CreativeEntityList(creatives).GetCreativeIds()
	adShareRecordMap, err := util.GetCreativeShareRecordMap(ctx, creativeIds)
	if err != nil {
		return resp.WithError(ctx, err)
	}
	creativeModels := make([]*model.CreativeModel, 0, len(creatives))
	for _, creative := range creatives {
		creativeModel := &model.CreativeModel{}
		creativeModel.FromEntity(ctx, creative)
		err := creativeModel.LoadMedia(ctx)
		if err != nil {
			ctx.LogE("load creative media failed", zap.Int64("id", adGroupModel.GroupId), zap.Error(err))
			continue
		}
		if len(adShareRecordMap) > 0 {
			if shareRecord, ok := adShareRecordMap[creativeModel.CreativeId]; ok {
				creativeModel.SetShareName(ctx, shareRecord.Extern
```

### `GetAdGroupRequirement` (creative-platform/app/adminapi/adgroup/adgroup_module.go)
```go
func (m *AdGroupModule) GetAdGroupRequirement(c *ginweb.Context, req *GetAdGroupRequirementRequest) ginweb.Response {

	ctx := ginbase.NewContext(c)
	identity := req.BuildQueryCondition(ctx)
	requirement, err := dao.GetCreativeRequirementByCondition(ctx, identity)
	if err != nil {
		return resp.WithError(ctx, err)
	}
	if requirement == nil {
		ctx.LogE("geo requirement not exist", zap.String("geo", *req.Geo))
		return ginweb.JSONResponse(http.StatusOK, errors.GinError(errors.PARTNER_REQUIREMENT_NOT_EXIST), nil)
	}

	requirementModel := &model.CreativeRequirementModel{}
	requirementModel.FromEntity(ctx, requirement)

	rsp := &GetAdGroupRequirementResponse{}
	rsp.ConstructResponse(ctx, requirementModel)
	return resp.WithSuccess(ctx, rsp)
}
```


## 测试覆盖报告
- 测试文件: 73
- 测试函数: 228
- 测试框架: goconvey
- 总函数数: 891
- 已测试函数: 50
- 覆盖率: 5.6%
- **未测试函数（样本）**:
  - `GetRefreshTokenLockKey`
  - `UpdateCreativeCenterCreativePackageByCondition`
  - `DoOneTask`
  - `TransactionSyncTask`
  - `GetGroupPauseTimeMap`
  - `FromUploadTaggingResult`
  - `QueryCreativePlatformRequestCreativeByCondition`
  - `GetAdminCache`
  - `CreateCreativeCenterCreativeDspSyncRelation`
  - `GetAdShareSheetStatusIndex`
  - `QueryCreativeRequirementByCondition`
  - `testGormDelete`
  - `SoftDeletePartner`
  - `SoftDeleteCreativeByCondition`
  - `Response`

## API 文档 (OpenAPI-like Spec)
共 134 个端点

- `Group /api/adgroup` → RequestLog
  - Request: `-` | Response: `-` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `POST /share/resend` → ShareResend
  - Request: `ShareResendRequest` | Response: `ctx` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `GET /hello/:operation` → Hello
  - Request: `HelloRequest` | Response: `ctx` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `POST /create` → CreateAdGroup
  - Request: `CreateAdGroupRequest` | Response: `ctx` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `POST /:group_id/edit` → EditAdGroup
  - Request: `EditAdGroupRequest` | Response: `ctx` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `Group /api/auth` → LoginCheck
  - Request: `-` | Response: `-` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `Group /api/auth` → RequestLog
  - Request: `-` | Response: `-` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `GET /login` → Login
  - Request: `-` | Response: `-` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `GET /permissions` → GetPermissions
  - Request: `-` | Response: `-` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `POST /logout` → LogOut
  - Request: `-` | Response: `-` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `Group /api/cp` → RequestLog
  - Request: `-` | Response: `-` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `POST configs/:module/save` → SaveConfigs
  - Request: `SaveConfigsRequest` | Response: `ctx` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `POST /configs` → GetConfigs
  - Request: `GetConfigsRequest` | Response: `ctx` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `POST /partner/save` → SavePartner
  - Request: `SavePartnerRequest` | Response: `ctx` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `GET /partner/:partner_id/detail` → GetPartnerDetail
  - Request: `GetPartnerDetailRequest` | Response: `ctx` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `Group /api/creative` → RequestLog
  - Request: `-` | Response: `-` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `GET /list` → ListCreatives
  - Request: `ListCreativesRequest` | Response: `ctx` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `POST /upload` → UploadCreative
  - Request: `UploadCreativeRequest` | Response: `ctx` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `GET /internal/download/:download_hash/:password/:group_id` → DownloadCreative
  - Request: `DownloadCreativeRequest` | Response: `ctx` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `GET /adgroup/list` → ListAdGroups
  - Request: `-` | Response: `-` | Middleware: LoginCheck, RequestLog, Context, PermissionCheck
- `Group /api/creative_platform/admin` → RequestLog
  - Request: `-` | Response: `-` | Middleware: LoginCheck, RequestLog, Context, AdminPermissionCheck
- `GET /trigger_callback` → TriggerCallback
  - Request: `TriggerCallbackRequest` | Response: `ctx` | Middleware: LoginCheck, RequestLog, Context, AdminPermissionCheck
- `GET /query_task_progress` → QueryTaskProgress
  - Request: `QueryTaskProgressRequest` | Response: `ctx` | Middleware: LoginCheck, RequestLog, Context, AdminPermissionCheck
- `GET /reset_task` → ResetTask
  - Request: `ResetTaskRequest` | Response: `ctx` | Middleware: LoginCheck, RequestLog, Context, AdminPermissionCheck
- `Group /api/creative_platform/asset_hub` → RequestLog
  - Request: `-` | Response: `-` | Middleware: RequestLog, Context
- `POST /asset/tagging` → UploadTaggingAsset
  - Request: `UploadTaggingAssetRequest` | Response: `ctx` | Middleware: RequestLog, Context
- `Group /api/creative_platform/creative_element` → RequestLog
  - Request: `-` | Response: `-` | Middleware: RequestLog, Context
- `POST /material/tagging` → UploadTaggingCreativeElement
  - Request: `UploadTaggingCreativeElementRequest` | Response: `ctx` | Middleware: RequestLog, Context
- `Group /api/creative_platform/creative_request` → RequestLog
  - Request: `-` | Response: `-` | Middleware: RequestLog, Context
- `POST /creative/upload` → UploadRequestTextCreatives
  - Request: `UploadRequestTextCreativesRequest` | Response: `ctx` | Middleware: RequestLog, Context

## SQL/GORM 操作 (Database Layer)
共 372 个数据库操作

操作类型分布:
- SELECT_ONE: 109
- INSERT: 67
- ORDER_BY: 54
- UPDATE: 41
- COUNT: 32
- FILTER: 22
- SELECT_COLUMNS: 18
- DELETE: 17
- INSERT_OR_UPDATE: 5
- RAW_SQL: 2
- EXEC_SQL: 2
- GROUP_BY: 2
- OFFSET: 1

- `db.Create` → INSERT (creative-platform/dao/admin_operation_log.go:22)
- `db.Count` → COUNT (creative-platform/dao/admin_operation_log.go:35)
- `db.Find` → SELECT_ONE (creative-platform/dao/admin_operation_log.go:53)
- `db.Create` → INSERT (creative-platform/dao/creativeplatform_request_creative.go:18)
- `db.Create` → INSERT (creative-platform/dao/creativeplatform_request_creative.go:33)
- `db.First` → SELECT_ONE (creative-platform/dao/creativeplatform_request_creative.go:46)
- `db.Find` → SELECT_ONE (creative-platform/dao/creativeplatform_request_creative.go:65)
- `db.Count` → COUNT (creative-platform/dao/creativeplatform_request_creative.go:81)
- `db.Select` → SELECT_COLUMNS (creative-platform/dao/creativeplatform_request_creative.go:102)
- `db.Update` → UPDATE (creative-platform/dao/creativeplatform_request_creative.go:135)
- `db.Delete` → DELETE (creative-platform/dao/creativeplatform_request_creative.go:400)
- `db.Find` → SELECT_ONE (creative-platform/dao/adshare_record.go:70)
- `db.Find` → SELECT_ONE (creative-platform/dao/adshare_record.go:90)
- `db.Find` → SELECT_ONE (creative-platform/dao/adshare_record.go:107)
- `db.Find` → SELECT_ONE (creative-platform/dao/adshare_record.go:125)
- `db.First` → SELECT_ONE (creative-platform/dao/adshare_record.go:142)
- `db.First` → SELECT_ONE (creative-platform/dao/adshare_record.go:159)
- `db.Delete` → DELETE (creative-platform/dao/adshare_record.go:177)
- `db.Update` → UPDATE (creative-platform/dao/adshare_record.go:190)
- `db.Find` → SELECT_ONE (creative-platform/dao/adshare_record.go:209)
- `db.Find` → SELECT_ONE (creative-platform/dao/adshare_record.go:226)
- `db.Create` → INSERT (creative-platform/dao/adgroup.go:30)
- `db.Create` → INSERT (creative-platform/dao/adgroup.go:41)
- `db.Update` → UPDATE (creative-platform/dao/adgroup.go:81)
- `db.Update` → UPDATE (creative-platform/dao/adgroup.go:113)
- `db.Count` → COUNT (creative-platform/dao/adgroup.go:162)
- `db.Count` → COUNT (creative-platform/dao/adgroup.go:186)
- `db.First` → SELECT_ONE (creative-platform/dao/adgroup.go:203)
- `db.Find` → SELECT_ONE (creative-platform/dao/adgroup.go:232)
- `db.Find` → SELECT_ONE (creative-platform/dao/adgroup.go:251)

## 错误码定义 (Error Codes)
共 238 个错误码

### general (10 codes)
- `SUCCESS` = 0: success
- `UNKOWN_ERROR` = 1: unknown error
- `INVALID_PARAMS` = 2: invalid params
- `NETWORK_ERROR` = 3: network error
- `SERVER_BUSY` = 4: server busy
- `SERVER_ERROR_AND_TRY_LATER` = 5: Server error, please try again later
- `EMPTY_PARAMS` = 6: empty params
- `SERVER_ERROR` = 7: server error
- `THIRD_SERVER_ERROR` = 8: third server error
- `API_PARTIALLY_FAILED` = 9: api response got partially failed

### database (6 codes)
- `DB_NOT_FOUND` = 101: not found from database
- `DB_DATA_DUPLICATE` = 102: insert data exists
- `DB_QUERY_FAIL` = 103: database query failed
- `DB_EXCUTE_FAIL` = 104: database execute failed
- `DB_TRANSACTION_FAIL` = 105: database transaction failed
- `DB_INVALID_PARAMS` = 106: database parameters is invalid

### redis (21 codes)
- `RDS_INCR_FAIL` = 201: redis incr failed
- `RDS_LOCK_IS_LOCKING` = 202: redis lock is locking by others
- `RDS_SET_FAIL` = 203: redis set failed
- `RDS_GET_FAIL` = 204: redis get failed
- `RDS_DEL_FAIL` = 205: redis del failed
- `RDS_EXPIRE_FAIL` = 206: redis expire failed
- `RDS_GET_EMPTY` = 207: redis get empty
- `RDS_DATA_NOT_EXIST` = 208: redis data does not exist
- `RDS_SMEM_FAIL` = 209: redis smembers failed
- `RDS_SADD_FAIL` = 210: redis sadd failed
  ... 还有 11 个

### http (8 codes)
- `HTTP_REQUEST_FAIL` = 301: http request failed
- `HTTP_READ_BODY_FAIL` = 302: http read body failed
- `HTTP_REQUEST_NO_BODY` = 303: http request no body
- `HTTP_NEW_REQUEST_FAIL` = 304: http new request fail
- `HTTP_INVALID_STATUS` = 305: http invalid status
- `HTTP_AUTH_FAILED` = 306: http auth failed
- `HTTP_RATE_LIMIT_EXCEED` = 307: http rate limit exceeded (429)
- `HTTP_REQUEST_TIMEOUT` = 308: http request timeout

### creative (2 codes)
- `USER_NOT_LOGIN` = 601: user not login
- `USER_NOT_FOUND` = 602: user not found

### imagestop (3 codes)
- `USER_NOT_PERMISSION` = 701: user no permission
- `WRONG_URL_PATH_TO_PREMISSION` = 702: wrong url path to error
- `PERMISSION_INVALID` = 703: user permission invalid

### other (177 codes)
- `JSON_FORMAT_ERROR` = 20004: request json format error
- `S3_CLIENT_INVALID` = 1100: s3 client invalid
- `S3_UPLOAD_FAIL` = 1101: s3 upload failed
- `S3_DOWNLOAD_FAIL` = 1102: s3 download failed
- `S3_DELETE_FAIL` = 1103: s3 delete failed
- `S3_LIST_FAIL` = 1104: s3 list failed
- `S3_MULTIPART_COMPLETION_ALREADY_IN_PROGRESS` = 1105: this multipart completion is already in progress
- `S3_FILE_NOT_EXIST` = 1106: s3 file not exists
- `HTTP_STATUS_NON_AUTHORITATIVE_INFO` = 901: http non authoritative info
- `HTTP_STATUS_UNAUTHORIZED` = 902: http unauthorized
  ... 还有 167 个

### adshare (11 codes)
- `BUSINESS_CONFIG_NOT_FOUND` = 801: business config not found
- `BUSINESS_CONFIG_MODULE_DUPLICATE` = 802: business config module duplicate
- `BUSINESS_CONFIG_MODULE_NOT_DEFINE` = 803: business config module not defined
- `BUSINESS_CONFIG_MUDULE_ITEM_DUPLICATE` = 804: business config module item duplicate
- `BUSINESS_CONFIG_MUDULE_ITEM_NOT_FOUND` = 805: business config module item not found
- `BUSINESS_CONFIG_MUDULE_NOT_SUPPORT_ADD` = 806: business config module not support add operation
- `BUSINESS_CONFIG_MUDULE_NOT_SUPPORT_EDIT` = 807: business config module not support edit operation
- `BUSINESS_CONFIG_MUDULE_NOT_SUPPORT_DELETE` = 808: business config module not support delete operation
- `BUSINESS_CONFIG_MUDULE_GEO_BINDING_FAILED` = 809: All partners are not available, please try again later
- `BUSINESS_CONFIG_SET_LAST_UPDATE_TIME_FAILED` = 810: business config set last updated time failed
  ... 还有 1 个

## 权限/鉴权模型 (Authentication & Authorization)
共 8 个中间件/鉴权组件

- **PermissionCheck** (creative-platform/app/adminapi/middleware/permission.go): cookie-based; redis-cache; token-validation; sso-integration; permission-check
- **AdminPermissionCheck** (creative-platform/app/adminapi/middleware/permission.go): cookie-based; redis-cache; token-validation; sso-integration; permission-check
- **Context** (creative-platform/app/adminapi/middleware/ctx_midware.go): unknown
- **AuthAccountCheck** (creative-platform/app/adminapi/middleware/auth.go): token-validation; sso-integration; permission-check
- **AdminOperationLogInit** (creative-platform/app/adminapi/middleware/admin_operation.go): unknown
- **RequestLog** (creative-platform/app/adminapi/middleware/request_log.go): unknown
- **LoginCheck** (creative-platform/app/adminapi/middleware/login.go): cookie-based; redis-cache; token-validation; sso-integration; permission-check
- **受保护路由**: 37 个路由需要登录认证

## Entity/TableName 映射 (Database Entities)
共 24 个实体表

- `TaskAdGroupRelationEntity` → `cp_task_ad_group_relation_tab` (creative-platform/dao/entity/task_adgroup_relation.go:14)
- `AdminOperationLogEntity` → `cp_admin_operation_log` (creative-platform/dao/entity/admin_operation_log.go:23)
- `LibraryMediaTagRelationEntity` → `cp_library_media_tag_relation_tab` (creative-platform/dao/entity/library_media_tag_log.go:13)
- `AdShareRecordEntity` → `cp_ad_share_record_tab` (creative-platform/dao/entity/adshare_record.go:27)
- `AdGroupEntity` → `cp_ad_group_tab` (creative-platform/dao/entity/adgroup.go:47)
- `OperationLogEntity` → `cp_operation_log_tab` (creative-platform/dao/entity/operation_log.go:19)
- `MediaEntity` → `cp_media_tab` (creative-platform/dao/entity/media.go:27)
- `CreativeRequirementEntity` → `cp_creative_requirement_tab` (creative-platform/dao/entity/creative_requirement.go:21)
- `ConfigModuleEntity` → `cp_config_module_tab` (creative-platform/dao/entity/config_module.go:18)
- `ConfigItemEntity` → `cp_config_item_tab` (creative-platform/dao/entity/config_item.go:26)
- `PartnerEntity` → `cp_partner_tab` (creative-platform/dao/entity/partner.go:30)
- `LibraryMediaVideoEntity` → `cp_library_media_video_tab` (creative-platform/dao/entity/library_media_video.go:28)
- `PermissionConfigEntity` → `cp_permission_config_tab` (creative-platform/dao/entity/permission_config.go:16)
- `LibraryMediaImageEntity` → `cp_library_media_image_tab` (creative-platform/dao/entity/library_media_image.go:25)
- `AdGroupPartnerRelationEntity` → `cp_ad_group_partner_relation_tab` (creative-platform/dao/entity/adgroup_partner_relation.go:18)
- `AdShareTaskGroupRelationEntity` → `cp_ad_share_task_group_relation_tab` (creative-platform/dao/entity/adshare_task_group_relation.go:15)
- `CreativeEntity` → `cp_creative_tab` (creative-platform/dao/entity/creative.go:31)
- `LibraryMediaContentEntity` → `cp_library_media_content_tab` (creative-platform/dao/entity/library_media_content.go:20)
- `AdShareSubTaskEntity` → `cp_ad_share_sub_task_tab` (creative-platform/dao/entity/ad_share_sub_task.go:23)
- `AdGroupPartnerTaskEntity` → `cp_ad_group_partner_task_tab` (creative-platform/dao/entity/adgroup_partner_task.go:18)
- `NotificationRecordEntity` → `cp_notification_record_tab` (creative-platform/dao/entity/notification_record.go:16)
- `AdShareSubTaskModuleEntity` → `cp_ad_share_sub_task_module_tab` (creative-platform/dao/entity/ad_share_sub_task_module.go:21)
- `RequestLogEntity` → `cp_request_log_tab` (creative-platform/dao/entity/request_log.go:21)
- `PartnerRequirementEntity` → `cp_partner_requirement_tab` (creative-platform/dao/entity/partner_requirement.go:25)

## Condition 查询条件 (Query Conditions)
共 54 个查询条件结构

- `TaskAdGroupRelationCondition` (creative-platform/dao/condition/task_adgroup_relation.go): [GroupRelationId, TaskId, GroupId, CreateTime, QueryOrder]
- `AdminOperationLogCondition` (creative-platform/dao/condition/admin_operation_log.go): [Id, ToolName, LowerToolName, ToolTypeCode, OperateTime]
  ... 还有 15 个字段
- `CreativePlatformRequestCreativeCondition` (creative-platform/dao/condition/creativeplatform_request_creative.go): [Id, CreativeId, CreativeHash, BatchCreativeHash, CreativeName]
  ... 还有 15 个字段
- `AdGroupCondition` (creative-platform/dao/condition/adgroup.go): [GroupId, AdGroupId, AdGroupSource, AdStartTime, for]
  ... 还有 15 个字段
- `AdGroupCampaignTimeCondition` (creative-platform/dao/condition/adgroup.go): [AdStartTime, for, group, date, AdEndTime1]
  ... 还有 13 个字段
- `AdGroupRunningDaysCondition` (creative-platform/dao/condition/adgroup.go): [OpStatus, AdStartTime]
- `MediaCondition` (creative-platform/dao/condition/media.go): [MediaId, Geo, MediaHash, IsDeleted, MediaType]
  ... 还有 15 个字段
- `CreativeCenterPackageCreativeRequirementCondition` (creative-platform/dao/condition/creativecenter_channel_requirement.go): [Id, CreativeType, Objective, CreativeRequirement, Creator]
  ... 还有 4 个字段
- `CreativeRequirementCondition` (creative-platform/dao/condition/creative_requirement.go): [RequirementId, Geo, RequirementType, MediaType, Creator]
  ... 还有 7 个字段
- `CreativePlatformSpexApiErrorRecordCondition` (creative-platform/dao/condition/creativeplatform_spex_api_error_record.go): [Id, Market, Operation, SpexApi, CallStatus]
  ... 还有 11 个字段
- `CreativeCenterCreativeDspSyncRelationCondition` (creative-platform/dao/condition/creativecenter_creative_dsp_sync_relation.go): [PackageDspSyncRelationId, MediaId, MediaType, Channel, MediaIdKey]
  ... 还有 4 个字段
- `ConfigModuleCondition` (creative-platform/dao/condition/config_module.go): [Id, ModuleCode, ModuleName, Creator, CreateTime]
  ... 还有 3 个字段
- `ImageStopCreativeSyncTaskCondition` (creative-platform/dao/condition/imagestop_creative_sync_task.go): [TaskId, TaskStatus, BeginTime, EndTime, CreativeTotal]
  ... 还有 8 个字段
- `ConfigItemCondition` (creative-platform/dao/condition/config_item.go): [Id, ModuleCode, ItemCode, ItemLevel, ItemValue]
  ... 还有 11 个字段
- `AdShareTaskCondition` (creative-platform/dao/condition/ad_share_task.go): [TaskId, TaskOp, TaskStatus, TaskSendType, TaskTimestamp]
  ... 还有 13 个字段

## 配置 (Configuration)
YAML: 75 项, JSON: 43 项

### creative-platform/etc/adminapi.yml
- `connect_timeout_seconds`: 10
- `- group`: off_platform_ads
- `project`: cp
- `namespace`: common_Config_<ENV>_default
- `non_live_secret`: 317f9231c83854fca3ce9dcbd0ed5a172cb69c60c44bbc2a0987739e88676e96

### creative-platform/etc/crontask.yml
- `connect_timeout_seconds`: 10
- `- group`: off_platform_ads
- `project`: cp
- `namespace`: common_Config_<ENV>_default
- `non_live_secret`: 317f9231c83854fca3ce9dcbd0ed5a172cb69c60c44bbc2a0987739e88676e96

### creative-platform/etc/drive.yml
- `connect_timeout_seconds`: 10
- `- group`: off_platform_ads
- `project`: cp
- `namespace`: common_Config_<ENV>_default
- `non_live_secret`: 317f9231c83854fca3ce9dcbd0ed5a172cb69c60c44bbc2a0987739e88676e96

## 性能热点 (Performance Hotspots)
共 91 个性能问题:
- UNLIMITED_QUERY: 91

- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/admin_operation_log.go:53): Query without Limit: db = db.Find(&res)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/creativeplatform_request_creative.go:65): Query without Limit: db = db.Find(&res)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/adshare_record.go:70): Query without Limit: db = db.Find(&res)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/adshare_record.go:90): Query without Limit: db = db.Find(&res)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/adshare_record.go:107): Query without Limit: db = db.Find(&res)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/adshare_record.go:125): Query without Limit: db = db.Find(&adShareRecord)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/adshare_record.go:209): Query without Limit: db = db.Find(&adShareRecord)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/adshare_record.go:226): Query without Limit: db = db.Find(&adShareRecord)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/adgroup.go:232): Query without Limit: db = db.Find(&res)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/adgroup.go:251): Query without Limit: db = db.Find(&res)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/adgroup.go:451): Query without Limit: db = db.Find(&res)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/media.go:64): Query without Limit: db = db.Find(&res)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/creative_requirement.go:19): Query without Limit: db = db.Find(&res)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/creative_requirement.go:39): Query without Limit: db = db.Find(&res)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/creativeplatform_spex_api_error_record.go:48): Query without Limit: db = db.Find(&res)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/creative_center_creative_package.go:35): Query without Limit: db = db.Find(&res)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/creative_center_creative_package.go:70): Query without Limit: db = db.Find(&res)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/creative_request_package_creative_relation.go:23): Query without Limit: db = db.Find(&res)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/creative_request_package_creative_relation.go:64): Query without Limit: db = db.Find(&res)
- **[H:medium]** `UNLIMITED_QUERY` (creative-platform/dao/creativecenter_creative_dsp_sync_relation.go:36): Query without Limit: db = db.Find(&res)

## 向后兼容 (Backward Compatibility)
共 484 个兼容问题:
- DEPRECATED: 484

- **[S:warning]** `DEPRECATED` (creative-platform/proto/spex/gen/go/marketplace_listing_item_itemaggregation_iteminfo.pb/marketplace_listing_item_itemaggregation_iteminfo.pb.go:4654): // Deprecated
- **[S:warning]** `DEPRECATED` (creative-platform/proto/spex/gen/go/item_fe_category.pb/item_fe_category.pb.go:150): // Deprecated API
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:112): // Deprecated: Use Constant_ErrorCode.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:197): // Deprecated: Use Constant_Region.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:249): // Deprecated: Use Constant_NodeStatus.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:304): // Deprecated: Use Constant_RequestStatus.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:359): // Deprecated: Use TemplateGroupGeneratorStatus_Status.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:414): // Deprecated: Use AssetRequestStatus_Status.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:469): // Deprecated: Use MediaType_Type.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:515): // Deprecated: Use Asset_AssetStatus.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:564): // Deprecated: Use Asset_UsageStatus.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:613): // Deprecated: Use Asset_AssetCreateSource.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:668): // Deprecated: Use Asset_AssetSource.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:726): // Deprecated: Use Asset_AssetType.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:778): // Deprecated: Use Asset_AssetChannel.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:851): // Deprecated: Use Asset_OpsCampaignType.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:909): // Deprecated: Use Asset_Objective.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:958): // Deprecated: Use Asset_TemplateSource.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:1004): // Deprecated: Use Asset_Hidden.Descriptor instead.
- **[S:critical]** `DEPRECATED` (creative-platform/proto/spex/gen/go/discover_design_core.pb/discover_design_core.pb.go:1050): // Deprecated: Use Tag_TagStatus.Descriptor instead.

---

请基于以上信息，输出以下结构化知识：

1. **架构总览** — 系统定位、技术栈、服务拆分、部署架构
2. **核心业务流程** — 主要业务场景的流程描述（用文字，不需要 mermaid）
3. **数据库表结构** — 表名、字段、ER 关系
4. **服务层架构** — Service/DAO/Model 分层说明
5. **外部系统集成** — 第三方 API、消息队列等
6. **术语 Glossary** — 业务术语及其含义