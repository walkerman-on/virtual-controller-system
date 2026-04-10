"""
Тот же расчёт PID, что в controller/universal_controller.PIDController.calculate,
без Telegram и лишних зависимостей — для нагрузочного эмулятора.
"""


class LoadTestPID:
    def __init__(
        self,
        kp: float,
        ki: float,
        kd: float,
        output_min: float = 0.0,
        output_max: float = 100.0,
        integral_limit: float = 10.0,
    ):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        self.integral_limit = integral_limit
        self.previous_error = 0.0
        self.integral = 0.0

    def calculate(self, setpoint: float, process_value: float, dt: float) -> float:
        if setpoint is None or process_value is None:
            return 50.0
        if dt <= 0:
            dt = 0.1

        action = 1
        error = action * (process_value - setpoint)

        P = self.kp * error
        self.integral += error * dt
        self.integral = max(-self.integral_limit, min(self.integral, self.integral_limit))
        I = (1.0 / self.ki) * self.integral if self.ki else 0.0

        if dt > 0:
            _ = self.kd * (error - self.previous_error) / dt
        op_start = 50.0
        output = P + I + op_start
        output = max(self.output_min, min(output, self.output_max))
        self.previous_error = error
        return output
