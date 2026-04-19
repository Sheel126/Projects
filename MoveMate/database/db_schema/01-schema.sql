/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


CREATE TABLE IF NOT EXISTS `user` (
    `usr_id` INT(11) UNSIGNED NOT NULL AUTO_INCREMENT,
    `usr_username` VARCHAR(150) NOT NULL,
    `usr_password` VARCHAR(255) NOT NULL,
    `usr_salt` VARCHAR(100) NOT NULL,
    PRIMARY KEY (`usr_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `calorie_tracking` (
  `ct_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `ct_usr_id` int(11) unsigned NOT NULL,
  `ct_item` VARCHAR(255) NOT NULL,
  `ct_calories` int(11) NOT NULL,
  `ct_date` DATE NOT NULL,
  PRIMARY KEY (`ct_id`),
  CONSTRAINT FOREIGN KEY (`ct_usr_id`) REFERENCES `user`(`usr_id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `water_tracking` (
  `wt_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `wt_usr_id` int(11) unsigned NOT NULL,
  `wt_item` VARCHAR(255) NOT NULL,
  `wt_water` int(11) NOT NULL,
  `wt_date` DATE NOT NULL,
  PRIMARY KEY (`wt_id`),
  CONSTRAINT FOREIGN KEY (`wt_usr_id`) REFERENCES `user`(`usr_id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `sleep_tracking` (
  `slt_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `slt_usr_id` int(11) unsigned NOT NULL,
  `slt_item` VARCHAR(255) NOT NULL,
  `slt_sleep` int(11) NOT NULL,
  `slt_date` DATE NOT NULL,
  PRIMARY KEY (`slt_id`),
  CONSTRAINT FOREIGN KEY (`slt_usr_id`) REFERENCES `user`(`usr_id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `steps_tracking` (
  `stt_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `stt_usr_id` int(11) unsigned NOT NULL,
  `stt_item` VARCHAR(255) NOT NULL,
  `stt_steps` int(11) NOT NULL,
  `stt_date` DATE NOT NULL,
  PRIMARY KEY (`stt_id`),
  CONSTRAINT FOREIGN KEY (`stt_usr_id`) REFERENCES `user`(`usr_id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `reminders` (
  `rem_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `rem_usr_id` int(11) unsigned NOT NULL,
  `rem_title` VARCHAR(255) NOT NULL,
  `rem_time` TIME NOT NULL,
  `rem_completed` BOOLEAN DEFAULT FALSE NOT NULL,
  `rem_category` VARCHAR(255) NOT NULL,
  PRIMARY KEY (`rem_id`),
  CONSTRAINT FOREIGN KEY (`rem_usr_id`) REFERENCES `user`(`usr_id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `goals` (
  `goal_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `goal_usr_id` int(11) unsigned NOT NULL,
  `goal_category` VARCHAR(255) NOT NULL,
  `goal_target` int(11) unsigned NOT NULL,
  PRIMARY KEY (`goal_id`),
  CONSTRAINT FOREIGN KEY (`goal_usr_id`) REFERENCES `user`(`usr_id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `user_goals` (
  `user_goal_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `usr_id` int(11) unsigned NOT NULL,
  `user_goal_title` VARCHAR(255) NOT NULL,
  `user_goal_completed` BOOLEAN DEFAULT FALSE NOT NULL,
  `user_goal_recommendation` TEXT NOT NULL,
  PRIMARY KEY (`user_goal_id`),
  CONSTRAINT FOREIGN KEY (`usr_id`) REFERENCES `user`(`usr_id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `streaks` (
  `streak_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `streak_usr_id` int(11) unsigned NOT NULL,
  `streaks` int(11) NOT NULL,
  PRIMARY KEY (`streak_id`),
  CONSTRAINT FOREIGN KEY (`streak_usr_id`) REFERENCES `user`(`usr_id`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;