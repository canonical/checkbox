#include <sys/ptrace.h>
#include <stdio.h>

int main() {
    if (ptrace(PTRACE_TRACEME, 0, 1, 0) < 0) {
        // if ptrace() call return a negative value -> fail (or program is already beeing ptraced?)
        return 1;
    }

    return 0;
}
