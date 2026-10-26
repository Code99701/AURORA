import Link from "next/link";
import { Brand } from "@/components/shared/brand";
import { APP_TAGLINE } from "@/lib/constants";
import styles from "./footer.module.css";

export function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.container}>
        <div className={styles.top}>
          <div className={styles.brandCol}>
            <Brand />
            <p className={styles.tagline}>{APP_TAGLINE}</p>
          </div>

          <div className={styles.column}>
            <span className={styles.columnTitle}>Product</span>
            <Link href="/" className={styles.link}>Features</Link>
            <Link href="/about" className={styles.link}>Architecture</Link>
            <Link href="/workspaces" className={styles.link}>Workspace App</Link>
          </div>

          <div className={styles.column}>
            <span className={styles.columnTitle}>Company</span>
            <Link href="/about" className={styles.link}>About Us</Link>
            <Link href="/contact" className={styles.link}>Contact</Link>
          </div>

          <div className={styles.column}>
            <span className={styles.columnTitle}>Legal</span>
            <span className={styles.link}>Privacy Policy</span>
            <span className={styles.link}>Terms of Service</span>
          </div>
        </div>

        <div className={styles.bottom}>
          <span>© {new Date().getFullYear()} AURORA. All rights reserved.</span>
          <span>Multilingual Evidence-Grounded Research</span>
        </div>
      </div>
    </footer>
  );
}
