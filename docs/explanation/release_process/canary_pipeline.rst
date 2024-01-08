.. _canary_pipeline:

Canary Pipeline
^^^^^^^^^^^^^^^
This is an example on how the whole pipeline can be implemented in Jenkins.

.. code-block:: groovy
    
    pipeline {
        agent any

        stages {
            stage('Run validation sub jobs') {
                steps {
                    script {
                        parallel (
                            "Checkbox series-22 for amd64": {
                                echo 'Running Canary on core22 amd64'
                                build job: 'checkbox-edge-validation-core22-amd64', wait: true, propagate: true
                            },
                            "Checkbox series-22 for arm64": {
                                echo 'Running Canary on core22 arm64'
                                build job: 'checkbox-edge-validation-core22-arm64', wait: true, propagate: true
                            },
                            "Checkbox series-16 for amd64": {
                                echo 'Running Canary on core16 amd64'
                                build job: 'checkbox-edge-validation-core16-amd64', wait: true, propagate: true
                            }

                        )
                    }
                }
            }
        }
        post {
            always {
                script {
                    def resultParam = currentBuild.resultIsBetterOrEqualTo('SUCCESS') ? 'edge-validation-succeeded' : 'edge-validation-failed'
                    // Trigger the job shifting the beta reference
                    build job: 'checkbox-edge-validation-move-beta', parameters: [string(name: 'RESULT', value: resultParam)]
                }
            }
        }
    }