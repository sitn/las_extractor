import os
import time
    
def remove_old_files(repository, timeout):
    """
        Delete temp files that are older than the number of timeout
        seconds and creates a repository directory if not existing
    """
    errorMessage=''
    files = os.listdir(repository)
    for file in files:
        filename = os.path.join(
                repository,
                file
            )
        age = time.time() - os.stat(filename).st_mtime
        if age > timeout and file != ".emptyfolder" and file != ".lock.log":
            try:
                os.remove(filename)
            except:
                errorMessage += filename
                
    return errorMessage

def check_directory(repository):
    """
        Creates a repository if it does not exist
    """
    
    if not os.path.exists(repository):
        os.makedirs(repository)