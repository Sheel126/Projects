/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


INSERT INTO user (usr_id, usr_username, usr_password, usr_salt) VALUES
    (1, 'student', '83d9bdb5e20f3571b087db9aabf190a296741c3e864d7742f35658cfccc1b79c4599aad25084aa9a28c649a50c92244227b3e53e197621301d619d1ea01873c4', '48c8947f69c054a5caa934674ce8881d02bb18fb59d5a63eeaddff735b0e9'),
    (2, 'graduate', 'e289219c34f9a32ebc82393f09719b7f34872de95463242b5ffe8bb4b11a5fe7d454f9f5d082c8207c5d69b220ba06624b4bb15ffa05cc7d7d53c43f9e96da6a', '801e87294783281ae49fc8287a0fd86779b27d7972d3e84f0fa0d826d7cb67dfefc');

INSERT INTO calorie_tracking(ct_id, ct_usr_id, ct_item, ct_calories) VALUES
    (1, 1, 'pizza', 500),
    (2, 1, 'cake', 500);

INSERT INTO water_tracking(wt_id, wt_usr_id, wt_item, wt_water) VALUES
    (1, 1, 'Glass', 2);

INSERT INTO sleep_tracking(slt_id, slt_usr_id, slt_item, slt_sleep) VALUES
    (1, 1, 'Bed', 5);

INSERT INTO steps_tracking(stt_id, stt_usr_id, stt_item, stt_steps) VALUES
    (1, 1, 'Walk', 500);

INSERT INTO reminders(rem_id, rem_usr_id, rem_title, rem_time) VALUES
    (1, 1, 'Workout', '05:00:00'),
    (2, 1, 'Lunch', '12:00:00');

INSERT INTO goals(goal_id, goal_usr_id, goal_category, goal_target) VALUES
    (1, 1, 'Calories', 2500),
    (2, 1, 'Water', 2),
    (3, 1, 'Sleep', 8),
    (4, 1, 'Steps', 10000)
    (5, 2, 'Calories', 3500),
    (6, 2, 'Water', 4),
    (7, 2, 'Sleep', 12),
    (8, 2, 'Steps', 5000)

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;