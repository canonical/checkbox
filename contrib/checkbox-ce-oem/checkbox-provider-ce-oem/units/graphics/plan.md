# clinfo 驗證的 canonical checkbox case 開發

## Manifest
unit: manifest entry
id: has_opencl_support
_name: Support OpenCL testing
value-type: bool


## Python Script 的設計

建立一個名為 clinfo_test.py, 支援三個固定參數, detect，resource, test。
- optional 參數設計
  - binary, -b
    - 目的: 讓使用者有能力指定 clinfo 的 binary 檔案。為了因應ubuntucore環境中，使用者使用自己 build 的 clinfo snap 進行驗證。
    - 範例: clinfo_test.py detect -b "${CLINFO_EXECUTABLE:-clinfo}"
    - 範例: clinfo_test.py resource -b "${CLINFO_EXECUTABLE:-clinfo}"
    - 範例: clinfo_test.py test -b "${CLINFO_EXECUTABLE:-clinfo}"


### detect
- 目的: 當我們宣稱有支援 opencl 時，且要驗證時，要用一個 canonical checkbox job 來檢查是否有任何 platform & device 被列出來
- 作法: clinfo_test.py detect -b "${CLINFO_EXECUTABLE:-clinfo}"
  1. 檢查 clinfo binary 是否存在，若不存在，直接報錯，並終止
  2. 使用 clinfo -v 印出 version
  3. 執行 使用 clinfo -l 驗證進行驗證
    - Pass: 有值的情況
      ```
      ubuntu@ubuntu:~$ sudo clinfo -l
      Platform #0: ARM Platform
      `-- Device #0: Mali-G57 r0p1
      ```
    - Fail: 沒有值的情況
      ```
      ubuntu@ubuntu:~$ sudo clinfo -l
      ```
- checkbox job id: ce-oem-graphics/detect_opencl

### resource
- 目的: 建立 Canonical Checkbox resource
- 使用方式: clinfo_test.py test -b "${CLINFO_EXECUTABLE:-clinfo}" -i "${CLINFO_IGNORE_PLATFORM_AND_DEVICE_LIST:-}"
- resource 參數設計
  - ignore, -i
    - 目的: 可能有些 platform + device 是不需要驗證或是客戶不想支援，因此就沒有必要進行後續的驗證
    - 環境變數 CLINFO_IGNORE_PLATFORM_AND_DEVICE_LIST 的範例
      - 'ARM Platform':'Mali-G57 r0p1','ARM Platform':'Mali-G59'
      - 'NVIDIA CUDA:NVIDIA RTX A4000'
- Output 如下:
  - 情境一: 沒有 platform 和 deivce
  ```
  ```
  - 情境二: 單一 platform + 單一 deivce
  ```
  platform: ARM Platform
  platform_number: 0
  device: Mali-G57 r0p1
  device_number: 0
  ignore: false
  ```
  - 情境三: 單一 platform + 多 deivces
  ```
  platform: ARM Platform
  platform_number: 0
  device: Mali-G57 r0p1
  device_number: 0
  ignore: false

  platform: ARM Platform
  platform_number: 0
  device: Mali-G59
  device_number: 1
  ignore: false
  ```
  - 情境四: 多 platform + 多 deivces
  ```
  platform: ARM Platform
  platform_number: 0
  device: Mali-G57 r0p1
  device_number: 0
  ignore: false

  platform: ARM Platform
  platform_number: 0
  device: Mali-G59
  device_number: 1
  ignore: false

  platform: NVIDIA CUDA
  platform_number: 1
  device: NVIDIA RTX A4000
  device_number: 0
  ignore: false
  ```
- 實際作法:
  - 使用 clinfo -l 時會出現如下的結果
  - 範例 1
    ```
    ubuntu@ubuntu:~$ sudo clinfo -l
          Platform #0: ARM Platform
          `-- Device #0: Mali-G57 r0p1
    ```
      - 如此一來就可以找出對應的 platform & device，ignore參數(假設沒有要被 ignore)搭配，組出如下的資訊
      ```
      platform: ARM Platform
      platform_number: 0
      device: Mali-G57 r0p1
      device_number: 0
      ignore: false
      ```
  - 範例 2
    ```
    ubuntu@ubuntu:~$ sudo clinfo -l
          Platform #0: ARM Platform
          `-- Device #0: Mali-G57 r0p1
          `-- Device #0: Mali-G59
          Platform #1: NVIDIA CUDA
          `-- Device #0: NVIDIA RTX A4000
    ```
      - 如此一來就可以找出對應的 platform & device，ignore參數('ARM Platform':'Mali-G59')搭配，組出如下的資訊
      ```
      platform: ARM Platform
      platform_number: 0
      device: Mali-G57 r0p1
      device_number: 0
      ignore: false

      platform: ARM Platform
      platform_number: 0
      device: Mali-G59
      device_number: 0
      ignore: true

      platform: NVIDIA CUDA
      platform_number: 1
      device: NVIDIA RTX A4000
      device_number: 0
      ignore: false
      ```
- checkbox job id: opencl_clinfo_resource

### test
1. test 參數設計
  - validation_json_path, -vjp
    - 目的: 一份 json 檔案的系統路徑。user 可以自定義要驗證的內容在該檔案中，以便有客製化驗證的能力。若為空，則進入預設的驗證內容，該內容被寫在 python script 內。
    - 範例: clinfo_test.py test -b "${CLINFO_EXECUTABLE:-clinfo}" -vjp "${CLINFO_VALIDATION_JSON_FILE:-}"
2. python script 內預設的 validation info
  - 目的: 提供一組適用於所有 architecture 的預設值
  - 若有指定 validation_json_path，則不使用該組預設值。
3. 驗證流程
  TBD