-- Run automatically on a new volume, or explicitly to add missing lab data.
-- Existing rows are preserved; rerunning this script does not duplicate seeds.
SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS minicloud
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE minicloud;
CREATE TABLE IF NOT EXISTS notes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO notes (title)
SELECT 'Hello from MariaDB!'
WHERE NOT EXISTS (SELECT 1 FROM notes WHERE title = 'Hello from MariaDB!');

CREATE DATABASE IF NOT EXISTS studentdb
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE studentdb;
CREATE TABLE IF NOT EXISTS students (
    id INT PRIMARY KEY AUTO_INCREMENT,
    student_id VARCHAR(10),
    fullname VARCHAR(100),
    dob DATE,
    major VARCHAR(50)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Synthetic Vietnamese student data, not actual student records.
INSERT INTO students (student_id, fullname, dob, major)
SELECT 'SV001', 'Nguyễn Minh An', '2004-03-15', 'Công nghệ thông tin'
WHERE NOT EXISTS (SELECT 1 FROM students WHERE student_id = 'SV001');

INSERT INTO students (student_id, fullname, dob, major)
SELECT 'SV002', 'Trần Ngọc Bình', '2004-07-22', 'Khoa học máy tính'
WHERE NOT EXISTS (SELECT 1 FROM students WHERE student_id = 'SV002');

INSERT INTO students (student_id, fullname, dob, major)
SELECT 'SV003', 'Lê Thu Chi', '2004-11-08', 'Hệ thống thông tin'
WHERE NOT EXISTS (SELECT 1 FROM students WHERE student_id = 'SV003');
