from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping


class ConfigValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    show_legal_moves: bool = True
    show_coordinates: bool = True
    animation_duration_ms: int = 160
    ai_enabled: bool = False
    ai_difficulty: str = "medium"
    ai_time_limit_ms: int = 1000
    vision_enabled: bool = False
    camera_device: str = "0"
    vision_confidence: float = 0.8
    robot_enabled: bool = False
    robot_port: str = ""
    robot_speed_percent: int = 20
    robot_dry_run: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    @classmethod
    def defaults(cls) -> "Config":
        return cls()

    def updated(self, changes: Mapping[str, Any]) -> "Config":
        schema = self._schema()
        values = self.to_dict()
        for section, section_changes in changes.items():
            if section not in schema or not isinstance(section_changes, Mapping):
                raise ConfigValidationError("invalid configuration section: %s" % section)
            for key, value in section_changes.items():
                if key not in schema[section]:
                    raise ConfigValidationError("unknown configuration field: %s.%s" % (section, key))
                expected = schema[section][key]
                self._validate(section, key, value, expected)
                values[section][key] = value
        return self._from_dict(values)

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        return {
            "board": {
                "show_legal_moves": self.show_legal_moves,
                "show_coordinates": self.show_coordinates,
                "animation_duration_ms": self.animation_duration_ms,
            },
            "ai": {
                "enabled": self.ai_enabled,
                "difficulty": self.ai_difficulty,
                "time_limit_ms": self.ai_time_limit_ms,
            },
            "vision": {
                "enabled": self.vision_enabled,
                "camera_device": self.camera_device,
                "confidence": self.vision_confidence,
            },
            "robot": {
                "enabled": self.robot_enabled,
                "port": self.robot_port,
                "speed_percent": self.robot_speed_percent,
                "dry_run": self.robot_dry_run,
            },
            "system": {
                "host": self.host,
                "port": self.port,
                "log_level": self.log_level,
            },
        }

    @staticmethod
    def _schema() -> Dict[str, Dict[str, type]]:
        return {
            "board": {"show_legal_moves": bool, "show_coordinates": bool, "animation_duration_ms": int},
            "ai": {"enabled": bool, "difficulty": str, "time_limit_ms": int},
            "vision": {"enabled": bool, "camera_device": str, "confidence": float},
            "robot": {"enabled": bool, "port": str, "speed_percent": int, "dry_run": bool},
            "system": {"host": str, "port": int, "log_level": str},
        }

    @staticmethod
    def _validate(section: str, key: str, value: Any, expected: type) -> None:
        valid_type = isinstance(value, (int, float)) and not isinstance(value, bool) if expected is float else type(value) is expected
        if not valid_type:
            raise ConfigValidationError("invalid type for %s.%s" % (section, key))
        ranges = {
            ("board", "animation_duration_ms"): (0, 2000),
            ("ai", "time_limit_ms"): (100, 60000),
            ("vision", "confidence"): (0.0, 1.0),
            ("robot", "speed_percent"): (1, 100),
            ("system", "port"): (1, 65535),
        }
        range_key = (section, key)
        if range_key in ranges and not ranges[range_key][0] <= value <= ranges[range_key][1]:
            raise ConfigValidationError("value out of range for %s.%s" % (section, key))
        choices = {
            "difficulty": ("easy", "medium", "hard"),
            "log_level": ("DEBUG", "INFO", "WARNING", "ERROR"),
        }
        if key in choices and value not in choices[key]:
            raise ConfigValidationError("invalid choice for %s.%s" % (section, key))

    @staticmethod
    def _from_dict(values: Mapping[str, Mapping[str, Any]]) -> "Config":
        return Config(
            show_legal_moves=values["board"]["show_legal_moves"],
            show_coordinates=values["board"]["show_coordinates"],
            animation_duration_ms=values["board"]["animation_duration_ms"],
            ai_enabled=values["ai"]["enabled"],
            ai_difficulty=values["ai"]["difficulty"],
            ai_time_limit_ms=values["ai"]["time_limit_ms"],
            vision_enabled=values["vision"]["enabled"],
            camera_device=values["vision"]["camera_device"],
            vision_confidence=float(values["vision"]["confidence"]),
            robot_enabled=values["robot"]["enabled"],
            robot_port=values["robot"]["port"],
            robot_speed_percent=values["robot"]["speed_percent"],
            robot_dry_run=values["robot"]["dry_run"],
            host=values["system"]["host"],
            port=values["system"]["port"],
            log_level=values["system"]["log_level"],
        )
