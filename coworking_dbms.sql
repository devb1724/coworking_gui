-- ========================================
-- Co-Working DBMS Project: Full Schema + Logic + Seed + Utilities
-- Run this whole file in MySQL Workbench
-- ========================================

-- Fresh database
DROP DATABASE IF EXISTS coworking_db;
CREATE DATABASE coworking_db CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE coworking_db;

-- ========================================
-- Tables
-- ========================================
CREATE TABLE company (
  company_id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(120) NOT NULL,
  gstin VARCHAR(20),
  email VARCHAR(120),
  phone VARCHAR(20),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_company_name (name)
);

CREATE TABLE member (
  member_id INT PRIMARY KEY AUTO_INCREMENT,
  company_id INT,
  full_name VARCHAR(120) NOT NULL,
  email VARCHAR(120) UNIQUE,
  phone VARCHAR(20),
  status ENUM('ACTIVE','INACTIVE') DEFAULT 'ACTIVE',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_member_company FOREIGN KEY (company_id)
    REFERENCES company(company_id) ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE TABLE plan (
  plan_id INT PRIMARY KEY AUTO_INCREMENT,
  plan_name VARCHAR(80) NOT NULL,
  type ENUM('HOT_DESK','DEDICATED_DESK','PRIVATE_OFFICE','MEETING_ROOM','DAY_PASS') NOT NULL,
  monthly_fee DECIMAL(10,2),
  hourly_fee DECIMAL(10,2),
  daypass_fee DECIMAL(10,2),
  active TINYINT(1) DEFAULT 1,
  UNIQUE KEY uk_plan_name (plan_name)
);

CREATE TABLE room (
  room_id INT PRIMARY KEY AUTO_INCREMENT,
  room_name VARCHAR(80) NOT NULL,
  kind ENUM('OPEN','DEDICATED','PRIVATE','MEETING') NOT NULL,
  capacity INT NOT NULL,
  hourly_rate DECIMAL(10,2),
  active TINYINT(1) DEFAULT 1,
  UNIQUE KEY uk_room_name (room_name)
);

CREATE TABLE amenity (
  amenity_id INT PRIMARY KEY AUTO_INCREMENT,
  amenity_name VARCHAR(80) NOT NULL,
  UNIQUE KEY uk_amenity_name (amenity_name)
);

CREATE TABLE room_amenity (
  room_id INT NOT NULL,
  amenity_id INT NOT NULL,
  PRIMARY KEY (room_id, amenity_id),
  FOREIGN KEY (room_id) REFERENCES room(room_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  FOREIGN KEY (amenity_id) REFERENCES amenity(amenity_id)
    ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE membership (
  membership_id INT PRIMARY KEY AUTO_INCREMENT,
  member_id INT NOT NULL,
  plan_id INT NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE,
  status ENUM('ACTIVE','PAUSED','CANCELLED') DEFAULT 'ACTIVE',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (member_id) REFERENCES member(member_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  FOREIGN KEY (plan_id) REFERENCES plan(plan_id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE booking (
  booking_id INT PRIMARY KEY AUTO_INCREMENT,
  member_id INT NOT NULL,
  room_id INT NOT NULL,
  start_time DATETIME NOT NULL,
  end_time DATETIME NOT NULL,
  status ENUM('CONFIRMED','CANCELLED') DEFAULT 'CONFIRMED',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (member_id) REFERENCES member(member_id),
  FOREIGN KEY (room_id) REFERENCES room(room_id)
);

CREATE TABLE invoice (
  invoice_id INT PRIMARY KEY AUTO_INCREMENT,
  member_id INT NOT NULL,
  invoice_date DATE DEFAULT (CURRENT_DATE),
  due_date DATE,
  status ENUM('DRAFT','ISSUED','PAID') DEFAULT 'DRAFT',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (member_id) REFERENCES member(member_id)
);

CREATE TABLE invoice_item (
  item_id INT PRIMARY KEY AUTO_INCREMENT,
  invoice_id INT NOT NULL,
  ref_type ENUM('PLAN','BOOKING','OTHER'),
  description VARCHAR(160),
  qty_hours DECIMAL(10,2),
  unit_price DECIMAL(10,2),
  line_total DECIMAL(10,2) AS (ROUND(qty_hours * unit_price,2)) STORED,
  FOREIGN KEY (invoice_id) REFERENCES invoice(invoice_id)
);

CREATE TABLE payment (
  payment_id INT PRIMARY KEY AUTO_INCREMENT,
  invoice_id INT NOT NULL,
  amount DECIMAL(10,2),
  method ENUM('CASH','UPI','CARD'),
  paid_on DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (invoice_id) REFERENCES invoice(invoice_id)
);

CREATE TABLE audit_log (
  audit_id BIGINT PRIMARY KEY AUTO_INCREMENT,
  table_name VARCHAR(64),
  action ENUM('INSERT','UPDATE','DELETE'),
  row_id VARCHAR(64),
  when_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================
-- Functions
-- ========================================
DELIMITER $$

DROP FUNCTION IF EXISTS fn_booking_hours $$
CREATE FUNCTION fn_booking_hours(p_booking_id INT)
RETURNS DECIMAL(10,2)
DETERMINISTIC
BEGIN
  DECLARE hrs DECIMAL(10,2);
  SELECT TIMESTAMPDIFF(MINUTE,start_time,end_time)/60 INTO hrs
  FROM booking WHERE booking_id=p_booking_id;
  RETURN ROUND(IFNULL(hrs,0),2);
END $$

DROP FUNCTION IF EXISTS fn_invoice_paid_amount $$
CREATE FUNCTION fn_invoice_paid_amount(p_invoice_id INT)
RETURNS DECIMAL(10,2)
DETERMINISTIC
BEGIN
  DECLARE amt DECIMAL(10,2);
  SELECT IFNULL(SUM(amount),0) INTO amt FROM payment WHERE invoice_id=p_invoice_id;
  RETURN ROUND(amt,2);
END $$

DROP FUNCTION IF EXISTS fn_invoice_total $$
CREATE FUNCTION fn_invoice_total(p_invoice_id INT)
RETURNS DECIMAL(10,2)
DETERMINISTIC
BEGIN
  DECLARE t DECIMAL(10,2);
  SELECT IFNULL(SUM(line_total),0) INTO t FROM invoice_item WHERE invoice_id=p_invoice_id;
  RETURN ROUND(t,2);
END $$

DELIMITER ;

-- ========================================
-- Triggers
-- ========================================
DELIMITER $$

-- Prevent overlapping confirmed bookings for the same room
DROP TRIGGER IF EXISTS trg_booking_overlap $$
CREATE TRIGGER trg_booking_overlap
BEFORE INSERT ON booking
FOR EACH ROW
BEGIN
  DECLARE cnt INT;
  SELECT COUNT(*) INTO cnt
  FROM booking
  WHERE room_id=NEW.room_id
    AND status='CONFIRMED'
    AND NEW.start_time<end_time AND NEW.end_time>start_time;
  IF cnt>0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Room already booked!';
  END IF;
END $$

-- Auto-update invoice status to PAID when fully paid
DROP TRIGGER IF EXISTS trg_payment_update $$ 
CREATE TRIGGER trg_payment_update
AFTER INSERT ON payment
FOR EACH ROW
BEGIN
  DECLARE total DECIMAL(10,2);
  DECLARE paid DECIMAL(10,2);
  SELECT fn_invoice_total(NEW.invoice_id) INTO total;
  SELECT fn_invoice_paid_amount(NEW.invoice_id) INTO paid;
  IF paid>=total THEN
    UPDATE invoice SET status='PAID' WHERE invoice_id=NEW.invoice_id;
  END IF;
END $$

-- Auto-create invoice + line item when a booking is inserted
DROP TRIGGER IF EXISTS trg_booking_to_invoice $$
CREATE TRIGGER trg_booking_to_invoice
AFTER INSERT ON booking
FOR EACH ROW
BEGIN
  DECLARE v_hours DECIMAL(10,2);
  DECLARE v_rate  DECIMAL(10,2);
  DECLARE v_roomname VARCHAR(80);
  DECLARE v_invoice INT;

  -- compute hours from the inserted row
  SET v_hours = TIMESTAMPDIFF(MINUTE, NEW.start_time, NEW.end_time) / 60.0;

  -- fetch room details
  SELECT room_name, hourly_rate
  INTO v_roomname, v_rate
  FROM room
  WHERE room_id = NEW.room_id;

  -- create the invoice header
  INSERT INTO invoice(member_id, invoice_date, status)
  VALUES (NEW.member_id, CURDATE(), 'ISSUED');

  SET v_invoice = LAST_INSERT_ID();

  -- add invoice line tied to this booking
  INSERT INTO invoice_item(invoice_id, ref_type, description, qty_hours, unit_price)
  VALUES (
    v_invoice,
    'BOOKING',
    CONCAT('Room ', v_roomname, ' (booking #', NEW.booking_id, ')'),
    ROUND(v_hours, 2),
    v_rate
  );
END $$

DELIMITER ;

-- ========================================
-- Procedures
-- ========================================
DELIMITER $$

DROP PROCEDURE IF EXISTS sp_book_room $$
CREATE PROCEDURE sp_book_room(
  IN p_member INT, IN p_room INT,
  IN p_start DATETIME, IN p_end DATETIME)
BEGIN
  -- Inserts a booking; trg_booking_overlap validates, trg_booking_to_invoice auto-invoices
  INSERT INTO booking(member_id,room_id,start_time,end_time)
  VALUES(p_member,p_room,p_start,p_end);
END $$

DROP PROCEDURE IF EXISTS sp_pay_invoice $$
CREATE PROCEDURE sp_pay_invoice(IN p_invoice INT, IN p_amt DECIMAL(10,2))
BEGIN
  INSERT INTO payment(invoice_id,amount,method) VALUES(p_invoice,p_amt,'UPI');
END $$

-- Manual invoicing for an existing booking (useful for historic data)
DROP PROCEDURE IF EXISTS sp_invoice_booking $$
CREATE PROCEDURE sp_invoice_booking(IN p_booking_id INT)
BEGIN
  DECLARE v_member INT;
  DECLARE v_room INT;
  DECLARE v_start DATETIME;
  DECLARE v_end DATETIME;
  DECLARE v_hours DECIMAL(10,2);
  DECLARE v_rate  DECIMAL(10,2);
  DECLARE v_roomname VARCHAR(80);
  DECLARE v_invoice INT;

  -- fetch booking
  SELECT member_id, room_id, start_time, end_time
  INTO v_member, v_room, v_start, v_end
  FROM booking
  WHERE booking_id = p_booking_id;

  IF v_member IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Booking not found';
  END IF;

  -- compute hours & room details
  SET v_hours = TIMESTAMPDIFF(MINUTE, v_start, v_end) / 60.0;

  SELECT room_name, hourly_rate
  INTO v_roomname, v_rate
  FROM room
  WHERE room_id = v_room;

  -- create invoice header
  INSERT INTO invoice(member_id, invoice_date, status)
  VALUES (v_member, CURDATE(), 'ISSUED');

  SET v_invoice = LAST_INSERT_ID();

  -- add invoice line
  INSERT INTO invoice_item(invoice_id, ref_type, description, qty_hours, unit_price)
  VALUES (
    v_invoice,
    'BOOKING',
    CONCAT('Room ', v_roomname, ' (booking #', p_booking_id, ')'),
    ROUND(v_hours, 2),
    v_rate
  );

  -- return the invoice id
  SELECT v_invoice AS invoice_id;
END $$

DELIMITER ;

-- ========================================
-- Views
-- ========================================
CREATE OR REPLACE VIEW v_active_members AS
SELECT m.member_id,m.full_name,c.name AS company
FROM member m LEFT JOIN company c ON m.company_id=c.company_id
WHERE m.status='ACTIVE';

CREATE OR REPLACE VIEW v_member_balances AS
SELECT i.member_id,
       SUM(fn_invoice_total(i.invoice_id)) AS total,
       SUM(fn_invoice_paid_amount(i.invoice_id)) AS paid,
       SUM(fn_invoice_total(i.invoice_id))-SUM(fn_invoice_paid_amount(i.invoice_id)) AS due
FROM invoice i GROUP BY i.member_id;

-- ========================================
-- Seed data
-- ========================================
INSERT INTO company(name,email,phone) VALUES
 ('Acme Analytics','ops@acme.com','9100001111'),
 ('Blue Pine Labs','hello@bluepine.io','9100002222');

INSERT INTO member(company_id,full_name,email,phone) VALUES
 (1,'Dev Bhargav Rao','dev.rao@example.com','9000000001'),
 (1,'Hruthvik','Reddy@example.com','9000000002');

INSERT INTO plan(plan_name,type,monthly_fee,hourly_fee) VALUES
 ('Hot Desk','HOT_DESK',4999,0),
 ('Meeting Room','MEETING_ROOM',0,600);

INSERT INTO room(room_name,kind,capacity,hourly_rate) VALUES
 ('Lotus MR-1','MEETING',6,600),
 ('Open Bay','OPEN',20,0);

INSERT INTO membership(member_id,plan_id,start_date)
VALUES(1,1,CURDATE());

-- ========================================
-- Optional demo (uncomment to test)
-- ========================================

-- Example booking that will auto-create an invoice via trg_booking_to_invoice:
-- CALL sp_book_room(1, 1, DATE_ADD(NOW(), INTERVAL 1 HOUR), DATE_ADD(NOW(), INTERVAL 3 HOUR));

-- Or manually invoice an existing booking (replace 3 with a real booking_id):
-- CALL sp_invoice_booking(3);

-- Check data
-- SELECT * FROM booking ORDER BY booking_id DESC;
-- SELECT * FROM invoice ORDER BY invoice_id DESC;
-- SELECT * FROM invoice_item ORDER BY item_id DESC;
-- SELECT * FROM v_member_balances;
