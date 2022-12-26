from hashlib import sha224
import sqlite3

class UserAPI:

    def __init__(self, conn = None):
        """
        Create a new API object.
        If `conn` is specified, this will be the db connection.
        Otherwise, open the default connection to `users.db` sqlite database.
        Upon creation, create the users table if it does not exist.
        """
        if conn is None:
            self.conn = sqlite3.connect('users.db')
            self.conn.row_factory = sqlite3.Row
        else:
            self.conn = conn
        self.create_table()

    def execute_query(self, query, params=()):
        """
        Execute the given query using the given params, using our db connection.
        Return all rows fetched as a result of the execution.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            self.conn.commit()
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.IntegrityError as e:
            # Print useful messages for uniqueness constraint violations.
            message_words = str(e).split()
            if message_words[0] == "UNIQUE":
                violation = message_words[-1].split('.')
                raise Exception(f"A {violation[0][:-1]} already exists with the given {violation[1]}.")
            raise e
    
    def create_table(self):
        """
        Create the users table in the db we are connected to, if it does not exist.
        """
        self.execute_query("""
                CREATE TABLE IF NOT EXISTS users (
                    pid INTEGER PRIMARY KEY AUTOINCREMENT,
                    uuid varchar(56) UNIQUE DEFAULT NULL,
                    username varchar(255) UNIQUE DEFAULT NULL,
                    name varchar(255) DEFAULT NULL,
                    email email(255) UNIQUE DEFAULT NULL,
                    sms varchar(25) UNIQUE DEFAULT NULL,
                    created timestamptz DEFAULT CURRENT_TIMESTAMP,
                    lastseen timestamptz DEFAULT NULL
                )
        """)

    @staticmethod
    def compute_uuid(args):
        """
        Compute a new uuid given the args for the user.
        The uuid is a sha224 hash of the email or sms provided.
        """
        try:
            arg = args['email'] if 'email' in args else args['sms']
        except Exception:
            raise Exception("Must specify valid email address or sms number.")
        return sha224(arg.encode()).hexdigest()

    def get_users(self, uuid = None):
        """
        Fetch user(s) from our users table.
        If no uuid arg is given, return a list of all users.
        If the uuid arg is given, return the single matching user.
        If such a user does not exist, return None.
        """
        if uuid is None:
            return self.execute_query("SELECT * FROM users")
        else:
            user = self.execute_query("SELECT * FROM users WHERE uuid = ?", (uuid,))
            return user[0] if len(user) > 0 else None

    def create_user(self, args):
        """
        Create a new user in our users table from the given args.
        Return the dictionary representation of the created user. 
        """
        uuid = UserAPI.compute_uuid(args)
        user = {**args, 'uuid': uuid}
        if 'username' not in user or user['username'] is None:
            if 'email' in args:
                user['username'] = args['email']
            else:
                user['username'] = args['sms']
        
        self.execute_query(
            "INSERT INTO users (uuid, username, name, email, sms) VALUES (?, ?, ?, ?, ?)",
            (user.get('uuid'), user.get('username'), user.get('name'), user.get('email'), user.get('sms'))
        )
        return self.get_users(uuid)

    def update_user(self, uuid, args):
        """
        Update the user with the specified uuid, changing the values given by args dict.
        If successful, return the dictionary representation of the updated user.
        If no such user is found, return None.
        """
        user = self.get_users(uuid)
        if user is None:
            return None
        updated = {**user, **args}
        self.execute_query(
            "UPDATE users SET username = ?, name = ?, email = ?, sms = ? WHERE uuid = ?",
            (updated.get('username'), updated.get('name'), updated.get('email'), updated.get('sms'), updated.get('uuid'))
        )
        return updated

    def delete_user(self, uuid):
        """
        Delete the specified user from our users table.
        Return the dictionary representations of this user before and after the operation.
        This will allow us to confirm if a deletion took place.
        """
        userBefore = self.get_users(uuid)
        self.execute_query(
            "DELETE FROM users WHERE uuid = ?",
            (uuid,)
        )
        userAfter = self.get_users(uuid)
        return userBefore, userAfter
