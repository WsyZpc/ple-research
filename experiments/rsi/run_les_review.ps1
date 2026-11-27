param(
    [string]$TaskRoot = '\\wsl.localhost\Ubuntu\home\wsyzpc1\ple_harness\data\tasks',
    [string]$Uri = 'http://127.0.0.1:18080/api/engine/flow',
    [string]$ExpectedSchema = 'docx',
    [ValidateSet('les-mesh-resolution', 'fill-compaction-acceptance', 'landscape-sheet-revision')]
    [string]$TaskId = 'les-mesh-resolution'
)

$ErrorActionPreference = 'Stop'
function ConvertFrom-ReviewJson([string]$Json) {
    try {
        if ($PSVersionTable.PSVersion.Major -le 5 -and $Json.Length -ge 2097152) {
            Add-Type -AssemblyName System.Web.Extensions
            $parser = New-Object System.Web.Script.Serialization.JavaScriptSerializer
            $parser.MaxJsonLength = $Json.Length
            return $parser.DeserializeObject($Json)
        }
        ConvertFrom-Json -InputObject $Json -ErrorAction Stop
    } catch {
        throw "Could not decode RSI JSON ($($Json.Length) characters; $($_.Exception.GetType().Name))."
    }
}
$task = Join-Path $TaskRoot $TaskId
$isFill = $TaskId -eq 'fill-compaction-acceptance'
$isLandscape = $TaskId -eq 'landscape-sheet-revision'
$materials = if ($isLandscape) { 'environment/filesystem' } else { 'environment/files' }
$taskDir = if ($isFill) { $TaskId } else { "$TaskId/$materials" }
# Windows PowerShell 5.1 attaches provider metadata to strings returned by Get-Content.
$instruction = [IO.File]::ReadAllText((Join-Path $task 'instruction.md'), [Text.Encoding]::UTF8)
if ([string]::IsNullOrWhiteSpace($instruction)) { throw "The instruction for $TaskId is empty." }
if (-not (Test-Path -LiteralPath (Join-Path $task $materials) -PathType Container)) {
    throw "The task materials directory is missing for $TaskId."
}
if ($isFill) {
    $attachments = Join-Path $task 'environment/tools/files/ce01-slab-on-grade-fill-compaction-acceptance-3d2c133e'
    foreach ($name in 'Fill_Placement_Records_BlockA_SlabOnGrade.xlsx', 'Thelbridge_Materials_Acceptance_Record_TEMPLATE.docx') {
        if (-not (Test-Path -LiteralPath (Join-Path $attachments $name) -PathType Leaf)) {
            throw "Missing fill compaction attachment: $name"
        }
    }
}
$request = @{
    flowId = if ($isLandscape) {
        '@com.horsecoder.common.whuTalent.flowTesting.core/FLOW_PLE_LANDSCAPE_REVIEW'
    } else {
        '@com.horsecoder.common.whuTalent.flowTesting.core/FLOW_PLE_ENTITY_REVIEW'
    }
    params = @{
        task_dir = $taskDir
        instruction = $instruction
        expected_schema = $ExpectedSchema
    }
} | ConvertTo-Json -Depth 6
Write-Host ("Submitting {0} ({1} instruction characters). Waiting for the backend..." -f $TaskId, $instruction.Length)
try {
    $response = Invoke-RestMethod -Method Post -Uri $Uri -Body ([Text.Encoding]::UTF8.GetBytes($request)) -ContentType 'application/json; charset=utf-8'
} catch {
    $status = $_.Exception.Response.StatusCode
    if ($null -ne $status) { throw "$TaskId HTTP request failed (status $([int]$status)). See the IDEA console for this request." }
    throw "$TaskId HTTP request failed ($($_.Exception.GetType().Name)). See the IDEA console for this request."
}
if ($response -is [string]) { $response = ConvertFrom-ReviewJson $response }
if (-not $response.data.value.result) { throw 'RSI did not return a flow blackboard.' }
$board = ConvertFrom-ReviewJson $response.data.value.result
if (($isFill -and -not $board.fill_compaction) -or
    ($isLandscape -and -not $board.trace_metrics.landscape_review) -or
    (-not $isFill -and -not $isLandscape -and -not $board.entity_review_extensions)) {
    throw 'The backend responded with the previous flow. Rebuild and restart AppTestStarter Windows.'
}
$board
