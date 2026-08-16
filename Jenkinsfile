pipeline {
    agent any
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Review') {
            steps {
                script {
                    def result = sh(
                        script: 'python3 scripts/pr_review_bot.py analyze --pr-data pr_data.json',
                        returnStdout: true
                    )
                    def analysis = readJSON text: result
                    
                    // 发布审查结果
                    publishHTML([
                        reportDir: 'review-reports',
                        reportFiles: 'review_report.html',
                        reportName: 'biz-delivery Review'
                    ])
                    
                    // 质量门禁
                    def gate = sh(
                        script: 'python3 scripts/pr_review_bot.py check',
                        returnStdout: true
                    )
                    def gateResult = readJSON text: gate
                    
                    if (!gateResult.passed) {
                        error("Quality gate failed: ${gateResult.rating}")
                    }
                }
            }
        }
        
        stage('Notify') {
            steps {
                slackSend(
                    channel: '#dev-reviews',
                    color: 'good',
                    message: "biz-delivery review completed: ${env.BUILD_NUMBER}"
                )
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
        failure {
            slackSend(
                channel: '#dev-alerts',
                color: 'danger',
                message: "biz-delivery review failed: ${env.BUILD_URL}"
            )
        }
    }
}
