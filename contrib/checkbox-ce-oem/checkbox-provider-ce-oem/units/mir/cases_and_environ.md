
## <a id='top'>environ keys for mir test</a>
- PLAINBOX_SESSION_SHARE
	- Affected Test Cases:
		- [mir/glmark2-es2-wayland-auto](#mir/glmark2-es2-wayland-auto)
- GL_VENDOR
	- Affected Test Cases:
		- [mir/glmark2-es2-wayland-auto](#mir/glmark2-es2-wayland-auto)
- GL_RENDERER
	- Affected Test Cases:
		- [mir/glmark2-es2-wayland-auto](#mir/glmark2-es2-wayland-auto)

## Detailed test cases
### <a id='mir/check-ubuntu-frame-launching-auto'>mir/check-ubuntu-frame-launching-auto</a>
- **environ :**  None
- **summary :**  Test if Ubuntu-Frame can be brought up
- **description :**  
```
None
```
- **command :**  
```
graphics_test.sh frame
```

[Back to top](#top)
### <a id='mir/glmark2-es2-wayland-auto'>mir/glmark2-es2-wayland-auto</a>
- **environ :**  PLAINBOX_SESSION_SHARE GL_VENDOR GL_RENDERER
- **summary :**  Run OpenGL ES 2.0 Wayland benchmark on the GPU
- **description :**  
```
None
```
- **command :**  
```
graphics_test.sh glmark2
```

[Back to top](#top)
