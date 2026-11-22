import contextlib
import io
import json
import runpy
import tempfile
from pathlib import Path
from unittest.mock import patch

mod = runpy.run_path(str(Path(__file__).resolve().parents[1] / "service/contest-lan"))
g = mod["start"].__globals__
for failure in ("timer","firewall","nm-reload","unmanage","ap-create","address","page","dns","ap","success"):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state = root / "active.json"
        units = set()
        events = []
        model = dict(address=False, fw=False, managed=True, connected=True)
        def step(name):
            events.append(name)
            if name == failure:
                raise RuntimeError("injected "+name)
        def cmd(*a, **kw):
            if a[0]=="systemd-run":
                step("timer")
                units.add("contest-lan-rollback.timer")
            elif a[:2]==("nft","-f"):
                step("firewall")
                model["fw"]=True
            elif a[:3]==("nmcli","-g","GENERAL.NM-MANAGED"): return "yes" if model["managed"] else "no"
            elif a[:3]==("nmcli","general","reload"):
                if (root/"nm.conf").exists(): step("nm-reload")
            elif a[:2]==("iw","phy"): step("ap-create")
            elif a[:3]==("nmcli","--wait","15"):
                step("disconnect")
                model["connected"]=False
            elif a[:3]==("nmcli","device","set"):
                if a[-1]=="no": step("unmanage")
                model["managed"]=a[-1]=="yes"
            elif a[:3]==("ip","addr","add"):
                step("address")
                model["address"]=True
            elif a[:3]==("ip","-j","addr"):
                return json.dumps([{"addr_info":[{"local":"10.50.0.1"}] if model["address"] else []}])
            elif a[:3]==("ip","addr","del"): model["address"]=False
            elif a[:3]==("nft","list","tables"): return "table inet contest_lan" if model["fw"] else ""
            elif a[:2]==("nft","delete"):
                assert "contest-lan-ap" not in units
                model["fw"]=False
            elif a[:3]==("nmcli","--wait","30"):
                assert not model["fw"] and model["managed"]
                model["connected"]=True
            elif a[:2]==("systemctl","stop"): units.discard(a[2])
            return ""
        def launch(unit,*a):
            step(unit.split("-")[-1])
            units.add(unit)
        def field(k):
            if k=="GENERAL.STATE": return "100 (connected)" if model["connected"] else "30 (disconnected)"
            return "profile-uuid" if model["connected"] else ""
        def test_path(*parts):
            if parts==("/sys/class/net","testusb"):
                return root
            return Path(*parts)
        with patch.dict(g, Path=test_path, BASE=Path("/opt/contest-lan"),ROOT=root,STATE=state,NM_CONF=root/"nm.conf", run=cmd,
                        launch=launch, loaded=units.__contains__,nm=field,check_live=lambda:None,
                        snapshot=lambda:dict(usb="testusb",version=3,uuid="profile-uuid",up=True,mode="a",channel=161,phy="phy0")), contextlib.redirect_stdout(io.StringIO()):
            try: g["start"]()
            except RuntimeError as exc: assert str(exc)=="injected "+failure
            else:
                assert failure=="success" and state.exists() and model["fw"]
                g["recover"]()
            g["recover"]()
            assert not state.exists() and not units
            assert not (root/"nm.conf").exists()
            model.pop("address")  # kernel removes addresses with their virtual interface
            assert model==dict(fw=False,managed=True,connected=True)
    print("passed",failure)
