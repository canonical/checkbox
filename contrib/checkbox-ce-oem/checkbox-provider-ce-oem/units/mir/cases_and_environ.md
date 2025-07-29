
## <a id='top'>environ keys for mir tests</a>

- PLAINBOX_SESSION_SHARE
    - Affected Test Cases:
        - [mir/glmark2-es2-wayland-auto](#mir/glmark2-es2-wayland-auto)
- GL_VENDOR
    - Affected Test Cases:
        - [mir/glmark2-es2-wayland-auto](#mir/glmark2-es2-wayland-auto)
- GL_RENDERER
    - Affected Test Cases:
        - [mir/glmark2-es2-wayland-auto](#mir/glmark2-es2-wayland-auto)

## Detailed test cases contains environ variable
### <a id='mir/glmark2-es2-wayland-auto'>mir/glmark2-es2-wayland-auto</a>
- **summary:**
Run OpenGL ES 2.0 Wayland benchmark on the GPU

- **description:**
```
None
```

- **file:**
[source file](jobs.pxu#L15)

- **environ:**
PLAINBOX_SESSION_SHARE GL_VENDOR GL_RENDERER

- **command:**
```
graphics_test.sh glmark2
```
[Back to top](#top)
