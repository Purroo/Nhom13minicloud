-- Lab evidence: modify only a new disposable row, then roll back.
-- InnoDB AUTO_INCREMENT values may advance even after ROLLBACK.
SET NAMES utf8mb4;
USE studentdb;
START TRANSACTION;

SELECT '1. SELECT: existing students' AS step;
SELECT id, student_id, fullname, dob, major FROM students ORDER BY id;

SELECT '2. INSERT: disposable student' AS step;
INSERT INTO students (student_id, fullname, dob, major)
VALUES ('DEMOCRUD', 'Sinh viên kiểm thử', '2004-01-01', 'Ngành ban đầu');
SET @demo_id = LAST_INSERT_ID();
SELECT * FROM students WHERE id = @demo_id;

SELECT '3. UPDATE: only the disposable student' AS step;
UPDATE students SET major = 'Điện toán đám mây' WHERE id = @demo_id;
SELECT * FROM students WHERE id = @demo_id;

SELECT '4. DELETE: only the disposable student' AS step;
DELETE FROM students WHERE id = @demo_id;
SELECT COUNT(*) AS demo_rows_after_delete FROM students WHERE id = @demo_id;

ROLLBACK;
SELECT '5. ROLLBACK: original student data preserved' AS step;
SELECT id, student_id, fullname, dob, major FROM students ORDER BY id;
