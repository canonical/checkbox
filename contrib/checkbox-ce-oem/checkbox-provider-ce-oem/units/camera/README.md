# Vendor Specific Camera Test Jobs

This document introduces the vendor-specific camera test jobs for MIPI camera systems.

## Resource Job

### `mipi_camera_resource`

This resource job requires the Checkbox environment variable `MIPI_SCENARIO_DEFINITION_FILE_PATH`.

**Required Environment Variable:**

- `MIPI_SCENARIO_DEFINITION_FILE_PATH`: Path to the JSON file that defines scenarios for target cameras to perform.

## Template Jobs

Two template jobs are generated based on the output of `mipi_camera_resource`:

### Image Capture Job

```text
id: mipi-camera/capture-image_{{ camera }}_{{ physical_interface }}_{{ method }}_{{ width }}x{{ height }}_{{ format }}
```

### Video Recording Job

```text
id: mipi-camera/record-video_{{ camera }}_{{ physical_interface }}_{{ method }}_{{ width }}x{{ height }}@{{ fps }}fps_{{ format }}
```

**Required Environment Variables:**

- `PLATFORM_NAME`: **Required** - The platform name of the Device Under Test (DUT). This variable is used to identify which project's code will be used for camera operations.

**Optional Environment Variables:**

- `MIPI_CAMERA_SETUP_CONF_FILE_PATH`: Path to the setup configuration file in JSON format (required if your camera needs to configure format/resolution of pads or set pad links)

## Code Structure

The code structure is as follows:

```text
camera_test.py -- Main entry point for all camera tests
├── camera_utils.py -- Common utilities, base classes, and shared functionality
├── camera_genio.py -- Genio platform-specific camera implementation
└── camera_<platform>.py -- Platform-specific implementations (e.g., camera_raspberry.py)
```

### How It Works

1. **Entry Point**: `camera_test.py` parses command-line arguments and determines the action
2. **Platform Detection**: Uses `PLATFORM_NAME` to identify which platform-specific code to load
3. **Dynamic Loading**: `camera_factory()` function loads the appropriate platform module
4. **Resource Generation**: For `generate_resource` action, processes scenario files to create test resources
5. **Test Execution**: For `testing` action, creates camera handler instance and executes the specified scenario
6. **Artifact Management**: Handles file creation, validation, and cleanup

**Key Functions:**

- `camera_factory()`: Dynamically loads platform-specific modules
- `list_device_by_v4l2_ctl()`: Discovers available V4L2 devices
- `MediaController`: Handles camera setup and configuration
- Platform-specific handlers: Execute actual camera operations

## Contributing: Adding New Platforms

To add support for a new platform, follow this structure:

### 1. Create Platform-Specific Module

Create `camera_<platform>.py` (e.g., `camera_raspberry.py`):

```python
#!/usr/bin/env python3
import logging
from enum import Enum
from typing import Union, Dict, List
from camera_utils import (
    CameraInterface,
    execute_command,
    SupportedMethods,
    CameraError,
    CameraConfigurationError,
    log_and_raise_error,
)

logger = logging.getLogger(__name__)

class SupportedCamera(Enum):
    """Supported camera modules on your platform."""
    CAMERA_MODEL_1 = "camera_model_1"
    CAMERA_MODEL_2 = "camera_model_2"

def <platform>_camera_factory(camera_module: str) -> CameraInterface:
    """
    Factory function to create camera handler instances.
    
    Args:
        camera_module: String identifier of the camera module
        
    Returns:
        Camera handler class that implements CameraInterface
    """
    camera_handlers = {
        str(SupportedCamera.CAMERA_MODEL_1): CameraModel1Handler,
        str(SupportedCamera.CAMERA_MODEL_2): CameraModel2Handler,
    }
    
    handler_class = camera_handlers.get(camera_module)
    if not handler_class:
        raise CameraError(
            "Unsupported camera module: {}. "
            "Supported modules are: {}".format(
                camera_module, list(camera_handlers.keys())
            )
        )
    return handler_class

class <Platform>BaseCamera(CameraInterface):
    """Base class for your platform camera implementations."""
    
    def __init__(self, v4l2_devices: str):
        super().__init__(v4l2_devices)
        self._v4l2_devices = v4l2_devices
        
    def capture_image(self, width: int, height: int, format: str, 
                     store_path: str, artifact_name: str, 
                     v4l2_device_name: str) -> str:
        """Implement image capture for your platform."""
        # Your platform-specific implementation
        pass
        
    def record_video(self, width: int, height: int, framerate: int, 
                    format: str, count: int, store_path: str, 
                    artifact_name: str, method: str, 
                    v4l2_device_name: str) -> str:
        """Implement video recording for your platform."""
        # Your platform-specific implementation
        pass

class CameraModel1Handler(<Platform>BaseCamera):
    """Handler for Camera Model 1."""
    def __init__(self, v4l2_devices: str):
        super().__init__(v4l2_devices)
        self._camera = SupportedCamera.CAMERA_MODEL_1

class CameraModel2Handler(<Platform>BaseCamera):
    """Handler for Camera Model 2."""
    def __init__(self, v4l2_devices: str):
        super().__init__(v4l2_devices)
        self._camera = SupportedCamera.CAMERA_MODEL_2
```

### 2. Update Factory Function

Add your platform to the `camera_factory()` function in `camera_utils.py` (e.g., `raspberry`):

```python
def camera_factory(platform: str, camera_module: str) -> object:
    if "genio" in platform:
        from camera_genio import genio_camera_factory
        return genio_camera_factory(camera_module=camera_module)
    elif "raspberry" in platform:  # Add your platform
        from camera_raspberry import raspberry_camera_factory
        return raspberry_camera_factory(camera_module=camera_module)
    else:
        log_and_raise_error(
            "Cannot find the '{}' platform".format(platform),
            CameraError,
        )
```

### 3. Create Configuration Files

Create test scenario and setup configuration files in the data directory:

```text
data/
├── <Platform>-MIPI-Camera-TestScenario-TestSetup/
│   ├── <platform>_camera_test_scenario_camera_model.json
│   ├── <platform>_camera_test_setup_camera_model.json
│   └── Test_Scenario_and_Test_Setup.md
```

### 4. Update Documentation

Add your platform to the documentation:

```markdown
### <Platform> Test Scenario and Test Setup Documentation

For comprehensive details about <Platform> configurations, refer to:

**[<Platform> Test Scenario and Test Setup Documentation](../../data/<Platform>-MIPI-Camera-TestScenario-TestSetup/Test_Scenario_and_Test_Setup.md)**
```

### 5. Required Implementation Methods

Your platform must implement these methods from `CameraInterface`:

- `capture_image()`: Capture still images
- `record_video()`: Record video streams

### 6. Testing Your Implementation

Test your platform with:

```bash
# Set environment variables
export PLATFORM_NAME=<platform>
export MIPI_SCENARIO_DEFINITION_FILE_PATH=path/to/your_scenario.json
export MIPI_CAMERA_SETUP_CONF_FILE_PATH=path/to/your_setup.json

# Generate resources
python3 camera_test.py generate_resource -sf path/to/your_scenario.json

# Run tests
python3 camera_test.py testing -sn capture_image -p <platform> -c camera_model_1 ...
```

### 7. Best Practices

- **Inherit from base classes**: Use `CameraInterface` and existing utilities
- **Error handling**: Use the provided exception classes
- **Logging**: Use the logger for debugging and information
- **Documentation**: Document your platform-specific requirements
- **Testing**: Test with multiple camera models and scenarios

## Real Example: Genio 350

### Configuration Details

- **Cameras**: Dual Onsemi Ap1302 + AR0430
- **Platform**: Genio 350

### Required Files

**Scenario Definition File** (`MIPI_SCENARIO_DEFINITION_FILE_PATH`):
[`genio_mipi_camera_test_scenario_AP1302_AR0430_dual.json`](../../data/Genio-MIPI-Camera-TestScenario-TestSetup/genio_mipi_camera_test_scenario_AP1302_AR0430_dual.json)

**Setup Configuration File** (`MIPI_CAMERA_SETUP_CONF_FILE_PATH`):
[`genio_mipi_camera_test_setup_AP1302_AR0430_dual.json`](../../data/Genio-MIPI-Camera-TestScenario-TestSetup/genio_mipi_camera_test_setup_AP1302_AR0430_dual.json)

### Environment Variable Configuration

```ini
PLATFORM_NAME=genio
MIPI_SCENARIO_DEFINITION_FILE_PATH=path/to/genio_mipi_camera_test_scenario_AP1302_AR0430_dual.json
MIPI_CAMERA_SETUP_CONF_FILE_PATH=path/to/genio_mipi_camera_test_setup_AP1302_AR0430_dual.json
```

## Platform Test Scenario and Test Setup Documentation

The following sections introduce the test scenario and test setup documentation for each platform.

### Genio Test Scenario and Test Setup Documentation

For comprehensive details about Genio platform configurations, test scenarios, and test setups, refer to:

**[Genio Test Scenario and Test Setup Documentation](../../data/Genio-MIPI-Camera-TestScenario-TestSetup/Test_Scenario_and_Test_Setup.md)**

This documentation includes:

- V4L2 Sensor Configurations
- Mediatek Imgsensor Configurations  
- Available camera models and their configurations
- Quick reference table for all supported configurations

## Troubleshooting

### Common Issues

1. **"Cannot find platform" error**
   - Ensure `PLATFORM_NAME` is set correctly
   - Check that platform module exists (e.g., `camera_genio.py`)

2. **"No video device node found" error**
   - Run `v4l2-ctl --list-devices` to verify device names
   - Check that camera is properly connected and detected

3. **JSON parsing errors**
   - Validate JSON syntax using online tools
   - Check for missing required fields in configuration files

4. **Permission denied errors**
   - Ensure user has access to `/dev/video*` devices
   - Run with appropriate permissions or add user to video group
