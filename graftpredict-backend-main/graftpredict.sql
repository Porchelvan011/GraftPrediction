-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Jan 30, 2026 at 10:29 PM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `graftpredict`
--

-- --------------------------------------------------------

--
-- Table structure for table `app_report`
--

CREATE TABLE `app_report` (
  `report_id` int(11) NOT NULL,
  `user_id` bigint(20) UNSIGNED NOT NULL,
  `email` varchar(255) NOT NULL,
  `Name` varchar(255) DEFAULT NULL,
  `Age` int(3) DEFAULT NULL,
  `Gender` enum('Male','Female','Other') DEFAULT NULL,
  `affected_side` enum('left knee','right knee') NOT NULL,
  `affected_date` date NOT NULL,
  `height` decimal(5,2) NOT NULL,
  `weight` decimal(5,2) NOT NULL,
  `bmi` decimal(5,2) NOT NULL,
  `leg_length` decimal(5,2) NOT NULL,
  `thigh_length` decimal(5,2) NOT NULL,
  `circumfrence_thigh` decimal(5,2) NOT NULL,
  `posterior_st` decimal(5,2) NOT NULL,
  `posterior_gracilis` decimal(5,2) NOT NULL,
  `lateral_st` decimal(5,2) NOT NULL,
  `lateral_gracilis` decimal(5,2) NOT NULL,
  `submission_time` timestamp NOT NULL DEFAULT current_timestamp(),
  `graft_diameter_1` decimal(5,2) DEFAULT NULL,
  `graft_diameter_2` decimal(5,2) DEFAULT NULL,
  `hamstring_autograft` decimal(5,2) DEFAULT NULL,
  `quadriceps_tendon_diameter` decimal(5,2) DEFAULT NULL,
  `minimum_st_length` decimal(5,2) DEFAULT NULL,
  `predicted_st_value` decimal(5,2) DEFAULT NULL,
  `gracilis_length` decimal(5,2) DEFAULT NULL,
  `pdf_report` longblob DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `app_report`
--

INSERT INTO `app_report` (`report_id`, `user_id`, `email`, `Name`, `Age`, `Gender`, `affected_side`, `affected_date`, `height`, `weight`, `bmi`, `leg_length`, `thigh_length`, `circumfrence_thigh`, `posterior_st`, `posterior_gracilis`, `lateral_st`, `lateral_gracilis`, `submission_time`, `graft_diameter_1`, `graft_diameter_2`, `hamstring_autograft`, `quadriceps_tendon_diameter`, `minimum_st_length`, `predicted_st_value`, `gracilis_length`, `pdf_report`) VALUES
(13, 81870782428, 'murugan@gmail.com', 'gandhi mahan', 46, 'Male', 'left knee', '2025-12-13', 180.00, 60.00, 18.50, 90.00, 40.00, 50.00, 6.00, 3.00, 8.00, 9.00, '2025-12-14 12:03:10', 5.00, 5.00, 7.00, 4.00, 57.00, 7.20, 44.00, NULL),
(16, 96384105049, 'ggiridharan39@gmail.com', 'Gopalakrishnan ', 48, 'Male', 'left knee', '2025-12-10', 182.00, 82.00, 24.80, 80.00, 42.00, 35.00, 5.10, 4.50, 3.80, 2.70, '2025-12-18 03:16:34', 5.00, 5.00, 4.40, 4.00, 52.60, 6.10, 40.40, NULL),
(20, 96384105049, 'ggiridharan39@gmail.com', 'ggiridharangonmad', 21, 'Male', 'left knee', '0000-00-00', 180.00, 60.00, 18.50, 90.00, 40.00, 50.00, 6.00, 3.00, 8.00, 9.00, '2026-01-18 18:59:39', 5.00, 5.00, 7.00, 4.00, 57.00, 7.20, 44.00, NULL),
(25, 27674798592, 'gopi@gmail.com', 'kadal kanni', 48, 'Female', 'right knee', '2026-01-24', 180.00, 85.00, 26.23, 90.00, 50.00, 40.00, 8.00, 3.00, 6.50, 4.40, '2026-01-23 20:42:04', 5.00, 5.00, 7.20, 4.00, 60.00, 9.60, 46.00, NULL),
(26, 27674798592, 'gopi@gmail.com', 'Mukesh C', 32, 'Male', 'left knee', '2025-12-19', 183.00, 74.00, 22.10, 100.00, 55.00, 60.00, 8.00, 3.00, 6.00, 9.00, '2026-01-24 02:29:48', 5.10, 5.00, 7.00, 4.00, 66.50, 9.60, 51.00, NULL);

-- --------------------------------------------------------

--
-- Table structure for table `password_reset`
--

CREATE TABLE `password_reset` (
  `email` varchar(255) NOT NULL,
  `otp` varchar(6) DEFAULT NULL,
  `expiry` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `password_reset`
--

INSERT INTO `password_reset` (`email`, `otp`, `expiry`) VALUES
('ggiridharan39@gmail.com', '088384', '2026-01-23 13:59:25');

-- --------------------------------------------------------

--
-- Table structure for table `shared_report`
--

CREATE TABLE `shared_report` (
  `sno` int(11) NOT NULL,
  `from_mail` varchar(50) NOT NULL,
  `to_mail` varchar(50) NOT NULL,
  `Date` date NOT NULL,
  `reort_no` int(11) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `shared_report`
--

INSERT INTO `shared_report` (`sno`, `from_mail`, `to_mail`, `Date`, `reort_no`) VALUES
(18, 'ggiridharan39@gmail.com', 'murugan@gmail.com', '2026-01-21', 22),
(24, 'ggiridharan39@gmail.com', 'murugan@gmail.com', '2026-01-22', 20),
(25, 'gopi@gmail.com', 'murugan@gmail.com', '2026-01-24', 26);

-- --------------------------------------------------------

--
-- Table structure for table `signin`
--

CREATE TABLE `signin` (
  `id` bigint(20) UNSIGNED NOT NULL COMMENT 'Unique ID for each user',
  `first_name` varchar(100) NOT NULL COMMENT 'User’s first name',
  `last_name` varchar(100) NOT NULL COMMENT 'User’s last name',
  `email` varchar(150) NOT NULL COMMENT 'User’s email (login identifier)',
  `password_hash` varchar(255) NOT NULL COMMENT 'Hashed password',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp() COMMENT 'Account creation time',
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp() COMMENT 'Last updated time',
  `user` varchar(10) NOT NULL DEFAULT 'Patient' COMMENT 'Doctor, Patient, Admin',
  `auth_provider` enum('local','google') NOT NULL DEFAULT 'local',
  `google_sub` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `signin`
--

INSERT INTO `signin` (`id`, `first_name`, `last_name`, `email`, `password_hash`, `created_at`, `updated_at`, `user`, `auth_provider`, `google_sub`) VALUES
(27674798592, 'Gopalakrishnan', 'V', 'gopi@gmail.com', '$2b$12$1/rTuq75Fa6IvxoYUgxVQOG.mtuH618wm8jAAQgFCi5ByzW3u0wuO', '2026-01-23 20:17:33', '2026-01-27 02:46:36', 'doctor', 'local', NULL),
(52362769951, 'saveetha', 'saveetha', 'admin@saveetha.com', '$2b$12$1aTc4R4czvmEEAB0.l5HUeSq7PhtOo3ztWNOJV/t4XJ26ezFACxbS', '2025-12-15 04:15:14', '2025-12-15 07:34:28', 'admin', 'local', NULL),
(80056182512, 'Giridhara', 'Byvyb', 'giri74428@gmail.com', '$2b$12$MVYPT7w0d7jGcJcl6BHtW.YYi9/UNVZyNue9wkeF/bOnDfd1E.lou', '2026-01-30 20:25:11', '2026-01-30 20:25:11', 'patient', 'local', NULL),
(81870782428, 'Murugan', 'Vadivel', 'murugan@gmail.com', '$2b$12$QBWxcMulwg4a7ep2A3mr/uqRdqfGD2/AwcQvz16.0XVwCt13KxXWy', '2025-12-09 15:32:51', '2026-01-23 19:39:11', 'doctor', 'local', NULL),
(96384105049, 'Giridharan', 'G', 'ggiridharan39@gmail.com', '$2b$12$O0hp1igmv3cnS9BlFtJ2xODrVyU6I.jesyxIgHepx904emgsy2EDy', '2025-12-16 07:32:09', '2026-01-30 21:14:55', 'patient', 'local', NULL);

-- --------------------------------------------------------

--
-- Table structure for table `user_details`
--

CREATE TABLE `user_details` (
  `id` bigint(20) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  `dob` date NOT NULL,
  `gender` enum('Male','Female','Other') NOT NULL,
  `age` int(11) NOT NULL,
  `language` enum('English','Tamil') NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `user_details`
--

INSERT INTO `user_details` (`id`, `user_id`, `dob`, `gender`, `age`, `language`, `created_at`, `updated_at`) VALUES
(15, 81870782428, '1999-07-10', 'Male', 34, 'English', '2025-12-14 11:51:14', '2025-12-14 11:51:14'),
(22, 96384105049, '2022-01-06', 'Male', 4, 'English', '2025-12-26 07:15:35', '2026-01-30 21:15:41'),
(24, 27674798592, '1977-05-20', 'Male', 48, 'English', '2026-01-23 20:17:33', '2026-01-23 20:17:33'),
(28, 80056182512, '2012-01-03', 'Female', 14, 'English', '2026-01-30 20:25:11', '2026-01-30 20:25:11');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `app_report`
--
ALTER TABLE `app_report`
  ADD PRIMARY KEY (`report_id`),
  ADD KEY `user_id` (`user_id`),
  ADD KEY `email` (`email`);

--
-- Indexes for table `password_reset`
--
ALTER TABLE `password_reset`
  ADD PRIMARY KEY (`email`);

--
-- Indexes for table `shared_report`
--
ALTER TABLE `shared_report`
  ADD PRIMARY KEY (`sno`);

--
-- Indexes for table `signin`
--
ALTER TABLE `signin`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `id` (`email`);

--
-- Indexes for table `user_details`
--
ALTER TABLE `user_details`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `app_report`
--
ALTER TABLE `app_report`
  MODIFY `report_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=29;

--
-- AUTO_INCREMENT for table `shared_report`
--
ALTER TABLE `shared_report`
  MODIFY `sno` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=27;

--
-- AUTO_INCREMENT for table `signin`
--
ALTER TABLE `signin`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT COMMENT 'Unique ID for each user', AUTO_INCREMENT=98454279091;

--
-- AUTO_INCREMENT for table `user_details`
--
ALTER TABLE `user_details`
  MODIFY `id` bigint(20) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=29;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
