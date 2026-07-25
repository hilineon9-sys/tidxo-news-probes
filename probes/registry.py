"""
探針自動註冊機制
"""
import importlib
import pkgutil
from pathlib import Path
from typing import Type
from .base import BaseProbe


class ProbeRegistry:
    """探針註冊表"""
    
    _probes: dict[str, Type[BaseProbe]] = {}
    
    @classmethod
    def register(cls, probe_class: Type[BaseProbe]) -> Type[BaseProbe]:
        """註冊探針"""
        if not probe_class.SOURCE_NAME:
            raise ValueError(f"Probe {probe_class.__name__} missing SOURCE_NAME")
        cls._probes[probe_class.SOURCE_NAME] = probe_class
        return probe_class
    
    @classmethod
    def get(cls, source_name: str) -> Type[BaseProbe]:
        """獲取探針"""
        if source_name not in cls._probes:
            raise KeyError(f"Probe '{source_name}' not found. Available: {list(cls._probes.keys())}")
        return cls._probes[source_name]
    
    @classmethod
    def all(cls) -> dict[str, Type[BaseProbe]]:
        """獲取所有已註冊探針"""
        return cls._probes.copy()
    
    @classmethod
    def list_sources(cls) -> list[str]:
        """列出所有可用新聞源"""
        return list(cls._probes.keys())


def get_registry() -> ProbeRegistry:
    """獲取註冊表"""
    return ProbeRegistry


def auto_discover_probes():
    """自動發現並註冊所有探針"""
    from probes import sources
    
    package_path = Path(sources.__file__).parent
    
    for _, module_name, _ in pkgutil.iter_modules([str(package_path)]):
        if module_name.startswith('_'):
            continue
        
        try:
            module = importlib.import_module(f"probes.sources.{module_name}")
            
            # 查找模組中的所有 BaseProbe 子類
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, BaseProbe) and 
                    attr is not BaseProbe and
                    attr.SOURCE_NAME):
                    ProbeRegistry.register(attr)
        except Exception as e:
            print(f"Warning: Failed to load probe {module_name}: {e}")
