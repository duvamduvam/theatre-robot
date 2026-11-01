import adafruit_bno055

class BNO055Extended(adafruit_bno055.BNO055_I2C):

    def __init__(self, i2c, calibration=None):
        super().__init__(i2c)
        if calibration:
            self.set_calibration(calibration)
        self.last_temperature = 0
    def get_calibration(self):
        """Return the sensor's calibration data and return it as an array of
        22 bytes. Can be saved and then reloaded with the set_calibration function
        to quickly calibrate from a previously calculated set of calibration data.
        """
        # Switch to configuration mode, as mentioned in section 3.10.4 of datasheet.
        self.mode = adafruit_bno055.CONFIG_MODE
        # Read the 22 bytes of calibration data and convert it to a list (from
        # a bytearray) so it's more easily serialized should the caller want to
        # store it.
        cal_data = list(self._read_registers(0X55, 22))
        # Go back to normal operation mode.
        self.mode = adafruit_bno055.NDOF_MODE
        return cal_data

    def set_calibration(self, data):
        """Set the sensor's calibration data using a list of 22 bytes that
        represent the sensor offsets and calibration data.  This data should be
        a value that was previously retrieved with get_calibration (and then
        perhaps persisted to disk or other location until needed again).
        """
        # Check that 22 bytes were passed in with calibration data.
        if data is None or len(data) != 22:
            raise ValueError('Expected a list of 22 bytes for calibration data.')
        # Switch to configuration mode, as mentioned in section 3.10.4 of datasheet.
        self.mode = adafruit_bno055.CONFIG_MODE
        # Set the 22 bytes of calibration data.
        self._write_register_data(0X55, data)
        # Go back to normal operation mode.
        self.mode = adafruit_bno055.NDOF_MODE

    def get_temperature(self):
        result = super().temperature
        if abs(result - self.last_temperature) == 128:
            result = super().temperature
            if abs(result - self.last_temperature) == 128:
                return 0b00111111 & result
        last_val = result
        return result

    def _write_register_data(self, register, data):
        write_buffer = bytearray(1)
        write_buffer[0] = register & 0xFF
        write_buffer[1:len(data)+1]=data
        with self.i2c_device as i2c:
            i2c.write(write_buffer, start=0, end=len(write_buffer))

    def _read_registers(self, register, length):
        read_buffer = bytearray(23)
        read_buffer[0] = register & 0xFF
        with self.i2c_device as i2c:
            i2c.write(read_buffer, start=0, end=1)
            i2c.readinto(read_buffer, start=0, end=length)
            return read_buffer[0:length]
