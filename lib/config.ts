import * as dotenv from 'dotenv';

dotenv.config();
export class Config {
  public readonly emailAddress: string;
  public readonly searchWindowDays: number;
  public readonly scheduleRate: number;
  public readonly githubRepo: string;
  public readonly emailToAddress: string;
  public readonly emailUsername: string;
  public readonly emailPassword: string;
  public readonly emailSmtpServer: string;
  public readonly emailSmtpPort: string;
  public readonly emailFromAddress: string;
  public readonly emailSubjectLine: string;
  public readonly alertEmailAddress: string;


  constructor(env: string) {
    this.emailToAddress = process.env.EMAIL_TO_ADDRESS || 'pamela.ocampo@gmail.com';
    this.emailUsername = process.env.EMAIL_USERNAME || 'pamela.ocampo@gmail.com';
    this.emailPassword = process.env.EMAIL_PASSWORD || '';
    this.emailSmtpServer = process.env.EMAIL_SMTP_SERVER || 'smtp.gmail.com';
    this.emailSmtpPort = process.env.EMAIL_SMTP_PORT || '465';
    this.emailFromAddress = process.env.EMAIL_FROM_ADDRESS || 'pamela.ocampo@gmail.com';
    this.emailSubjectLine = process.env.EMAIL_SUBJECT_LINE || 'Camply Notification';
    this.alertEmailAddress = process.env.ALERT_EMAIL_ADDRESS || 'pamela.ocampo@gmail.com';

    switch (env) {
      case 'prod':
        this.emailAddress = process.env.EMAIL_USERNAME || 'pamela.ocampo@gmail.com';
        this.searchWindowDays = 365;
        this.scheduleRate = 30;
        this.githubRepo = 'pamo/camply-checker-cdk';
        break;
      case 'dev':
      default:
        this.emailAddress = process.env.EMAIL_USERNAME || 'pamela.ocampo@gmail.com';
        this.searchWindowDays = 30;
        this.scheduleRate = 60;
        this.githubRepo = 'pamo/camply-checker-cdk';
        break;
    }
  }
}
