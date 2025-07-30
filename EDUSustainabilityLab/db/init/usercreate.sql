-- Drop user only if it exists
DROP USER IF EXISTS 'myuser1'@'%';

-- Create the user again
CREATE USER 'myuser1'@'%' IDENTIFIED BY 'pass1';

-- Grant full privileges
GRANT ALL PRIVILEGES ON *.* TO 'myuser1'@'%' WITH GRANT OPTION;
FLUSH PRIVILEGES;
