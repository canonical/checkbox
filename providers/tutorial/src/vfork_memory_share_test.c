#include <unistd.h>
#include <stdio.h>

#define MAGIC_NUMBER 24

static pid_t shared;

int main(void){
  int pid = vfork();
  if(pid != 0){
    // we are in parent, we can't rely on us being suspended
    // so let's give the children process 1s to write to the shared variable
    // if we are not
    if(shared != MAGIC_NUMBER){
      printf("Parent wasn't suspended when spawning child, waiting\n");
      sleep(1);
    }
    if(shared != MAGIC_NUMBER){
      printf("Child failed to set the variable\n");
    }else{
      printf("Child set the variable, vfork shares the memory\n");
    }
    return shared != MAGIC_NUMBER;
  }
  // we are in children, we should now write to shared, parent will
  // discover this if vfork implementation uses mamory sharing as expected
  shared = MAGIC_NUMBER;
  _exit(0);
}
