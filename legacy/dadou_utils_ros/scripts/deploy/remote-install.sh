  #!/bin/bash

source $UTILS_SCRIPTS/colors.sh
source $UTILS_SCRIPTS/params.sh

printf "\n${RED}FIRST $PROJECT_NAME INSTALL${YELLOW}\n\n"

ssh -t $USER_HOST sudo cp -rf $RPI_HOME/.ssh/ /root/

ssh -o SendEnv=$RPI_SCRIPTS -t $USER_HOST "cd $RPI_SCRIPTS;bash -s < $RPI_SCRIPTS/project-deploy.sh 'read_param';bash -s < $RPI_SCRIPTS/local-install.sh \n\n"