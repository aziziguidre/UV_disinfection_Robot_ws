import React, { useState, useEffect, useRef } from 'react';
import ROSLIB from 'roslib';
import {
  ShieldAlert,
  Sparkles,
  Play,
  Pause,
  Square,
  Home,
  Activity,
  Zap,
  MapPin,
  AlertTriangle,
  Radio,
  Compass,
  Maximize2,
  RefreshCw,
  Cpu,
  Power,
  PowerOff,
  Plus,
  Minus,
  Camera,
  UserCheck,
  UserX,
  Check,
  Flame,
  Map,
  Video,
  DoorOpen,
  Gauge,
  ScrollText,
  Radiation,
  BatteryMedium,
  Minimize2,
  Terminal,
  Trash2,
  ChevronUp,
  ChevronDown,
  CheckCircle2,
  Info,
  Clock
} from 'lucide-react';

/* ════════════════════════════════════════════════════════════════
   MAP_META — Standard map.png (543×1181)
   ox: -17.572123, oy: -38.071483, res: 0.05, w: 543, h: 1181
   ════════════════════════════════════════════════════════════════ */
const MAP_META = {
  src: '/map.png',
  w: 543,
  h: 1181,
  res: 0.05,
  ox: -17.572123,
  oy: -38.071483,
  worldW: 543 * 0.05,
  worldH: 1181 * 0.05,
};

const ROOM_COLORS = [
  '#0d9488', '#0284c7', '#6366f1', '#8b5cf6', '#d97706',
  '#059669', '#0891b2', '#4f46e5', '#7c3aed', '#ea580c',
  '#10b981', '#2563eb', '#9333ea', '#ca8a04'
];

export default function App() {
  const [connected, setConnected] = useState(false);
  const rosRef = useRef(null);

  const [currentTime, setCurrentTime] = useState(
    new Date().toLocaleTimeString('en-GB', { hour12: false })
  );

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString('en-GB', { hour12: false }));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const [roomStatus, setRoomStatus] = useState({
    room: 'IDLE', phase: 'idle', progress: 0,
    waypoint: 0, total_waypoints: 0, coverage: 0
  });

  const [disinfectionStats, setDisinfectionStats] = useState('Disinfected: 0.0% (0/0)');
  const [coveragePct, setCoveragePct] = useState(0.0);
  const [odomVel, setOdomVel] = useState(0.0);
  const [batteryState, setBatteryState] = useState(100);

  const DEFAULT_HOME = { x: -11.883, y: 10.879, yaw: 0.0 };
  const [homePose, setHomePose] = useState(DEFAULT_HOME);
  const [robotPose, setRobotPose] = useState({ x: -11.883, y: 10.879, yaw: 0.0 });
  const [minObstacleDist, setMinObstacleDist] = useState(999.0);
  const [pointCloudCount, setPointCloudCount] = useState(0);

  const [humanDetected, setHumanDetected] = useState(false);
  const [humanCount, setHumanCount] = useState(0);
  const prevHumanRef = useRef(false);

  const [roomList, setRoomList] = useState([]);
  const [roomCompletion, setRoomCompletion] = useState({});
  const [roomStats, setRoomStats] = useState({});
  const [disinfectionRunning, setDisinfectionRunning] = useState(false);

  const [logs, setLogs] = useState([
    { id: 1, text: 'Clinical Disinfection System initialized.', type: 'info', time: new Date().toLocaleTimeString() }
  ]);
  const [logFilter, setLogFilter] = useState('all');
  const [logExpanded, setLogExpanded] = useState(true);

  const [eStopActive, setEStopActive] = useState(false);
  const [cameraConnected, setCameraConnected] = useState(true);

  const mapCanvasRef = useRef(null);
  const mapImgRef = useRef(null);
  const mapImgLoadedRef = useRef(false);
  const dosePointsRef = useRef([]);

  const [viewCenter, setViewCenter] = useState({
    x: MAP_META.ox + MAP_META.worldW / 2,
    y: MAP_META.oy + MAP_META.worldH / 2
  });
  const [zoomScale, setZoomScale] = useState(1);
  const initialFitRef = useRef({ scale: 1, center: { x: 0, y: 0 } });

  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const dragStartCenterRef = useRef({ x: 0, y: 0 });
  const dragDistRef = useRef(0);
  const homeCapturedRef = useRef(false);
  const [renderTick, setRenderTick] = useState(0);

  const addLog = (text, type = 'info') => {
    setLogs((prev) => [
      { id: Date.now() + Math.random(), text, type, time: new Date().toLocaleTimeString() },
      ...prev.slice(0, 49)
    ]);
  };

  const resetFit = () => {
    const canvas = mapCanvasRef.current;
    if (!canvas || canvas.width === 0 || canvas.height === 0) return;
    const dpr = window.devicePixelRatio || 1;
    const fitScaleX = (canvas.width * 0.94) / (MAP_META.worldH * dpr);
    const fitScaleY = (canvas.height * 0.94) / (MAP_META.worldW * dpr);
    const fitScale = Math.min(fitScaleX, fitScaleY);
    const fitCenter = {
      x: MAP_META.ox + MAP_META.worldW / 2,
      y: MAP_META.oy + MAP_META.worldH / 2
    };
    initialFitRef.current = { scale: fitScale, center: fitCenter };
    setViewCenter(fitCenter);
    setZoomScale(fitScale);
    setRenderTick((t) => t + 1);
  };

  // Load rooms.json
  useEffect(() => {
    fetch('/rooms.json')
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          const mapped = data.map((r, i) => {
            const cx = r.center[0], cy = r.center[1];
            const dx = r.door[0], dy = r.door[1];
            return {
              ...r, centerX: cx, centerY: cy, doorX: dx, doorY: dy,
              hasSeparateDoor: Math.hypot(dx - cx, dy - cy) > 0.05,
              color: ROOM_COLORS[i % ROOM_COLORS.length]
            };
          });
          setRoomList(mapped);
          setRoomCompletion((prev) => {
            const n = { ...prev };
            mapped.forEach((nr) => { if (!n[nr.name]) n[nr.name] = 'pending'; });
            return n;
          });
          addLog(`Loaded ${mapped.length} hospital facility rooms`, 'success');
        }
      })
      .catch(() => {});
  }, []);

  // ResizeObserver — re-fit on every resize
  useEffect(() => {
    const canvas = mapCanvasRef.current;
    if (!canvas) return;
    const container = canvas.parentElement;
    const ro = new ResizeObserver(() => {
      const rect = container.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      canvas.style.width = rect.width + 'px';
      canvas.style.height = rect.height + 'px';
      resetFit();
    });
    ro.observe(container);
    return () => ro.disconnect();
  }, []);

  // Load map.png
  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      mapImgRef.current = img;
      mapImgLoadedRef.current = true;
      resetFit();
    };
    img.src = MAP_META.src;
  }, []);

  // ROS subscriptions
  useEffect(() => {
    const ros = new ROSLIB.Ros({ url: 'ws://localhost:9090' });
    rosRef.current = ros;

    ros.on('connection', () => { setConnected(true); addLog('ROS 2 bridge online', 'success'); });
    ros.on('error', (e) => { setConnected(false); addLog(`ROS 2 bridge error: ${e?.message || ''}`, 'error'); });
    ros.on('close', () => { setConnected(false); addLog('ROS 2 bridge disconnected', 'warning'); });

    new ROSLIB.Topic({ ros, name: '/amcl_pose', messageType: 'geometry_msgs/PoseStamped' }).subscribe((msg) => {
      const p = msg.pose.position, q = msg.pose.orientation;
      const yaw = Math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z));
      setRobotPose({ x: p.x, y: p.y, yaw });
      if (!homeCapturedRef.current && (Math.abs(p.x) > 0.01 || Math.abs(p.y) > 0.01)) {
        homeCapturedRef.current = true;
        setHomePose({ x: p.x, y: p.y, yaw });
      }
    });

    new ROSLIB.Topic({ ros, name: '/odom', messageType: 'nav_msgs/Odometry' }).subscribe((msg) => {
      const vx = msg.twist.twist.linear.x, vy = msg.twist.twist.linear.y;
      setOdomVel(Math.sqrt(vx * vx + vy * vy));
    });

    new ROSLIB.Topic({ ros, name: '/scan', messageType: 'sensor_msgs/LaserScan' }).subscribe((msg) => {
      if (msg.ranges && msg.ranges.length > 0) {
        const valid = msg.ranges.filter((r) => r > 0.05 && r < 30.0 && !isNaN(r));
        if (valid.length > 0) setMinObstacleDist(Math.min(...valid));
      }
    });

    new ROSLIB.Topic({ ros, name: '/uvrobot/disinfection_stats', messageType: 'std_msgs/String' }).subscribe((msg) => {
      setDisinfectionStats(msg.data);
      try { const m = msg.data.match(/([\d.]+)%/); if (m) setCoveragePct(parseFloat(m[1])); } catch (e) {}
    });

    new ROSLIB.Topic({ ros, name: '/uvrobot/human_detected', messageType: 'std_msgs/Bool' }).subscribe((msg) => {
      const detected = Boolean(msg.data);
      setHumanDetected(detected);
      if (detected !== prevHumanRef.current) {
        prevHumanRef.current = detected;
        if (detected) {
          addLog('⚠ SAFETY INTERLOCK: Human detected in room — UV radiation strictly BANNED and halted!', 'error');
          setDisinfectionRunning(false);
        } else {
          addLog('✓ Safety clear: Room clear of persons — UV interlock released', 'success');
        }
      }
    });

    new ROSLIB.Topic({ ros, name: '/uvrobot/human_count', messageType: 'std_msgs/Int32' }).subscribe((msg) => {
      setHumanCount(msg.data);
    });

    new ROSLIB.Topic({ ros, name: '/room/status', messageType: 'std_msgs/String' }).subscribe((msg) => {
      try {
        const st = JSON.parse(msg.data);
        setRoomStatus(st);
        if (st.room && st.room !== 'IDLE' && st.room !== 'Home') {
          const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
          setRoomCompletion((prev) => {
            const c = { ...prev };
            if (st.phase === 'held') c[st.room] = 'held';
            else if (st.phase === 'sweeping' || st.phase === 'transit') c[st.room] = 'sweeping';
            else if (st.phase === 'waiting' || st.phase === 'done') c[st.room] = 'waiting';
            return c;
          });
          setRoomStats((prev) => {
            const cur = prev[st.room] || { coverage: 0, lastTime: null };
            return {
              ...prev,
              [st.room]: {
                coverage: (st.phase === 'waiting' || st.phase === 'done') ? Math.max(cur.coverage, Math.round(st.progress * 100)) : (cur.coverage || Math.round(st.progress * 100)),
                lastTime: (st.phase === 'waiting' || st.phase === 'done') ? nowStr : cur.lastTime
              }
            };
          });
        }
        if (st.phase === 'stopped') setEStopActive(true);
        if (st.disinfection_running !== undefined) setDisinfectionRunning(st.disinfection_running);
      } catch (e) {}
    });

    let lastDoseTime = 0;
    new ROSLIB.Topic({ ros, name: '/uvrobot/irradiation_map', messageType: 'sensor_msgs/PointCloud2' }).subscribe((msg) => {
      const now = Date.now();
      if (now - lastDoseTime < 2000) return;
      lastDoseTime = now;
      if (msg.width && msg.width > 0) {
        setPointCloudCount(msg.width);
        try {
          const points = [];
          const dv = new DataView(new Uint8Array(msg.data).buffer);
          const pointStep = msg.point_step || 16;
          let xOff = 0, yOff = 4;
          if (msg.fields) { msg.fields.forEach((f) => { if (f.name === 'x') xOff = f.offset; if (f.name === 'y') yOff = f.offset; }); }
          for (let i = 0; i < msg.width; i++) {
            const base = i * pointStep;
            if (base + yOff + 4 <= dv.byteLength) {
              const px = dv.getFloat32(base + xOff, true), py = dv.getFloat32(base + yOff, true);
              if (isFinite(px) && isFinite(py)) points.push({ x: px, y: py });
            }
          }
          dosePointsRef.current = points;
          setRenderTick((t) => t + 1);
        } catch (e) {}
      }
    });

    return () => ros.close();
  }, []);

  // Wheel zoom
  useEffect(() => {
    const canvas = mapCanvasRef.current;
    if (!canvas) return;
    const handleWheel = (e) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      const cw = canvas.width / (window.devicePixelRatio || 1);
      const ch = canvas.height / (window.devicePixelRatio || 1);
      const wx = viewCenter.x - (my - ch / 2) / zoomScale;
      const wy = viewCenter.y - (mx - cw / 2) / zoomScale;
      const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
      const ns = Math.max(0.2, Math.min(60, zoomScale * factor));
      setZoomScale(ns);
      setViewCenter({ x: wx + (my - ch / 2) / ns, y: wy + (mx - cw / 2) / ns });
    };
    canvas.addEventListener('wheel', handleWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', handleWheel);
  }, [viewCenter, zoomScale]);

  // Transit ETA
  const targetRoomObj = roomList.find((r) => r.name === roomStatus.room);
  const transitDist = targetRoomObj ? Math.hypot(targetRoomObj.centerX - robotPose.x, targetRoomObj.centerY - robotPose.y) : 0;
  const transitEtaSec = Math.max(4, Math.round(transitDist / Math.max(0.25, odomVel || 0.35)));

  /* ══════════════════ CANVAS RENDER ══════════════════ */
  useEffect(() => {
    const canvas = mapCanvasRef.current;
    if (!canvas || canvas.width === 0 || canvas.height === 0) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const cw = canvas.width / dpr, ch = canvas.height / dpr;

    ctx.clearRect(0, 0, cw, ch);
    ctx.fillStyle = '#f1f5f9';
    ctx.fillRect(0, 0, cw, ch);
    ctx.strokeStyle = '#e2e8f0';
    ctx.lineWidth = 1;
    for (let x = 0; x < cw; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, ch); ctx.stroke(); }
    for (let y = 0; y < ch; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(cw, y); ctx.stroke(); }

    ctx.save();
    ctx.translate(cw / 2, ch / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.translate(-cw / 2, -ch / 2);

    const sx = (wx) => (wx - viewCenter.x) * zoomScale + cw / 2;
    const sy = (wy) => (viewCenter.y - wy) * zoomScale + ch / 2;

    if (mapImgRef.current && mapImgLoadedRef.current) {
      const { ox, oy, w, h, res } = MAP_META;
      ctx.drawImage(mapImgRef.current, sx(ox), sy(oy + h * res), w * res * zoomScale, h * res * zoomScale);
    }

    const dosePoints = dosePointsRef.current;
    if (dosePoints.length > 0) {
      const dotSize = Math.max(2, 0.15 * zoomScale);
      ctx.globalAlpha = 0.65;
      for (let i = 0; i < dosePoints.length; i++) {
        const dp = dosePoints[i], px = sx(dp.x), py = sy(dp.y);
        if (px > -40 && px < cw + 40 && py > -40 && py < ch + 40) {
          ctx.fillStyle = '#f97316';
          ctx.fillRect(px - dotSize / 2, py - dotSize / 2, dotSize, dotSize);
        }
      }
      ctx.globalAlpha = 1.0;
    }

    roomList.forEach((rm) => {
      const btnX = sx(rm.centerX), btnY = sy(rm.centerY);
      const isCurrent = roomStatus.room === rm.name;
      const isDone = roomCompletion[rm.name] === 'waiting';

      if (rm.hasSeparateDoor) {
        const doorX = sx(rm.doorX), doorY = sy(rm.doorY);
        ctx.save();
        ctx.strokeStyle = isCurrent ? '#2563EB' : 'rgba(148,163,184,0.6)';
        ctx.lineWidth = 1; ctx.setLineDash([2, 3]);
        ctx.beginPath(); ctx.moveTo(doorX, doorY); ctx.lineTo(btnX, btnY); ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = isCurrent ? '#2563EB' : '#94a3b8';
        ctx.beginPath(); ctx.arc(doorX, doorY, 3, 0, Math.PI * 2); ctx.fill();
        ctx.restore();
      }

      ctx.save();
      ctx.translate(btnX, btnY);
      ctx.rotate(Math.PI / 2);
      ctx.font = 'bold 11px sans-serif';
      const tw = ctx.measureText(rm.name).width;
      const btnW = Math.max(70, tw + 20), btnH = 24;
      const rx = -btnW / 2, ry = -btnH / 2;

      if (isCurrent) { ctx.fillStyle = '#2563EB'; ctx.strokeStyle = '#1d4ed8'; ctx.lineWidth = 2; }
      else if (isDone) { ctx.fillStyle = '#ecfdf5'; ctx.strokeStyle = '#059669'; ctx.lineWidth = 1.4; }
      else { ctx.fillStyle = 'rgba(255,255,255,0.96)'; ctx.strokeStyle = rm.color || '#cbd5e1'; ctx.lineWidth = 1.4; }

      const rad = 6;
      ctx.beginPath();
      ctx.moveTo(rx + rad, ry); ctx.lineTo(rx + btnW - rad, ry);
      ctx.quadraticCurveTo(rx + btnW, ry, rx + btnW, ry + rad);
      ctx.lineTo(rx + btnW, ry + btnH - rad);
      ctx.quadraticCurveTo(rx + btnW, ry + btnH, rx + btnW - rad, ry + btnH);
      ctx.lineTo(rx + rad, ry + btnH);
      ctx.quadraticCurveTo(rx, ry + btnH, rx, ry + btnH - rad);
      ctx.lineTo(rx, ry + rad);
      ctx.quadraticCurveTo(rx, ry, rx + rad, ry);
      ctx.closePath(); ctx.fill(); ctx.stroke();

      ctx.fillStyle = isCurrent ? '#ffffff' : isDone ? '#065f46' : '#1e293b';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(rm.name, 0, 0);
      ctx.restore();
    });

    if (homePose) {
      const hx = sx(homePose.x), hy = sy(homePose.y);
      ctx.strokeStyle = '#2563EB'; ctx.lineWidth = 1.5; ctx.setLineDash([4, 4]);
      ctx.beginPath(); ctx.arc(hx, hy, 14, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
      ctx.save(); ctx.translate(hx, hy + 22); ctx.rotate(Math.PI / 2);
      ctx.fillStyle = '#2563EB'; ctx.font = 'bold 10px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText('HOME', 0, 0); ctx.restore();
    }

    const rpx = sx(robotPose.x), rpy = sy(robotPose.y);
    ctx.save(); ctx.translate(rpx, rpy); ctx.rotate(-robotPose.yaw);
    ctx.fillStyle = '#2563EB'; ctx.beginPath(); ctx.arc(0, 0, 11, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = '#334155'; ctx.beginPath();
    ctx.arc(-4, -4, 2, 0, Math.PI * 2); ctx.arc(4, -4, 2, 0, Math.PI * 2);
    ctx.arc(-4, 4, 2, 0, Math.PI * 2); ctx.arc(4, 4, 2, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#93c5fd'; ctx.beginPath();
    ctx.moveTo(13, 0); ctx.lineTo(7, -5); ctx.lineTo(7, 5); ctx.closePath(); ctx.fill();
    ctx.restore();

    ctx.restore();
  }, [robotPose, homePose, roomStatus, roomCompletion, coveragePct, roomList, viewCenter, zoomScale, renderTick]);

  // Actions
  const sendRoomGoal = (roomName) => {
    if (eStopActive) {
      addLog(`Goal "${roomName}" blocked: Safety interlock active (E-Stop). Click Reset on the emergency banner to resume.`, 'error');
      return;
    }
    addLog(`Target: ${roomName}`, 'info');
    setRoomStatus((prev) => ({ ...prev, room: roomName, phase: 'transit', progress: 0.05, waypoint: 1, total_waypoints: 3 }));
    setRoomCompletion((prev) => ({ ...prev, [roomName]: 'sweeping' }));
    if (rosRef.current && connected) {
      new ROSLIB.Topic({ ros: rosRef.current, name: '/room/goal', messageType: 'std_msgs/String' }).publish(new ROSLIB.Message({ data: roomName }));
    }
  };

  const sendCommand = (cmd) => {
    if (eStopActive && cmd !== 'resume') {
      addLog(`Command "${cmd}" blocked: Emergency Stop is active. Click Reset first.`, 'error');
      return;
    }

    if (cmd === 'estop') {
      setEStopActive(true);
      setRoomStatus((p) => ({ ...p, phase: 'stopped' }));
      if (rosRef.current && connected) {
        new ROSLIB.Topic({ ros: rosRef.current, name: '/disinfection/stop', messageType: 'std_msgs/Bool' }).publish(new ROSLIB.Message({ data: true }));
        new ROSLIB.Topic({ ros: rosRef.current, name: '/room/command', messageType: 'std_msgs/String' }).publish(new ROSLIB.Message({ data: 'estop' }));
      }
      sendDisinfectionCommand('stop');
      addLog('EMERGENCY STOP ENGAGED — Navigation & UV radiation locked. System requires Reset.', 'error');
      return;
    }

    if (cmd === 'pause') {
      setRoomStatus((p) => ({ ...p, phase: 'paused' }));
      if (rosRef.current && connected) {
        new ROSLIB.Topic({ ros: rosRef.current, name: '/room/command', messageType: 'std_msgs/String' }).publish(new ROSLIB.Message({ data: 'pause' }));
      }
      addLog('Navigation PAUSED — robot holding current position.', 'warning');
      return;
    }

    if (cmd === 'resume') {
      setEStopActive(false);
      setRoomStatus((p) => ({ ...p, phase: p.phase === 'paused' ? 'transit' : 'idle' }));
      if (rosRef.current && connected) {
        new ROSLIB.Topic({ ros: rosRef.current, name: '/room/command', messageType: 'std_msgs/String' }).publish(new ROSLIB.Message({ data: 'resume' }));
      }
      addLog('Navigation RESUMED — continuing route.', 'success');
      return;
    }

    if (!rosRef.current || !connected) {
      if (cmd === 'start_tour') { sendRoomGoal(roomList.length > 0 ? roomList[0].name : 'Storage 1'); }
      else if (cmd === 'return_home') sendRoomGoal('Home');
      return;
    }

    new ROSLIB.Topic({ ros: rosRef.current, name: '/room/command', messageType: 'std_msgs/String' }).publish(new ROSLIB.Message({ data: cmd }));
    addLog(`Command: ${cmd}`, 'info');
  };

  const sendDisinfectionCommand = (cmd) => {
    if (cmd === 'start' && humanDetected) {
      addLog('UV activation BLOCKED: Person detected in room! Optical safety interlock active.', 'error');
      return;
    }
    if (!rosRef.current || !connected) { setDisinfectionRunning(cmd === 'start'); return; }
    const srvName = cmd === 'start' ? '/start_disinfection' : '/stop_disinfection';
    new ROSLIB.Service({ ros: rosRef.current, name: srvName, serviceType: 'std_srvs/Trigger' }).callService(new ROSLIB.ServiceRequest({}), (res) => {
      if (res?.message) addLog(`Disinfection: ${res.message}`, res?.success ? 'info' : 'error');
      if (cmd === 'start' && res?.success) setDisinfectionRunning(true);
      if (cmd === 'stop') setDisinfectionRunning(false);
    });
    const topicName = cmd === 'start' ? '/disinfection/start' : '/disinfection/stop_server';
    new ROSLIB.Topic({ ros: rosRef.current, name: topicName, messageType: 'std_msgs/Empty' }).publish(new ROSLIB.Message({}));
    addLog(`UV dose server ${cmd === 'start' ? 'started' : 'stopped'}`, 'info');
  };

  // Mouse handlers (90° rotation inverse)
  const handleMouseDown = (e) => {
    if (e.button !== 0) return;
    setIsDragging(true);
    dragStartRef.current = { x: e.clientX, y: e.clientY };
    dragStartCenterRef.current = { ...viewCenter };
    dragDistRef.current = 0;
  };
  const handleMouseMove = (e) => {
    if (!isDragging) return;
    const dx = e.clientX - dragStartRef.current.x, dy = e.clientY - dragStartRef.current.y;
    dragDistRef.current = Math.hypot(dx, dy);
    setViewCenter({ x: dragStartCenterRef.current.x + dy / zoomScale, y: dragStartCenterRef.current.y + dx / zoomScale });
  };
  const handleMouseUp = () => setIsDragging(false);
  const handleDoubleClick = () => resetFit();
  const handleCanvasClick = (e) => {
    if (dragDistRef.current > 5 || roomList.length === 0 || eStopActive) return;
    const canvas = mapCanvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const cw = canvas.width / (window.devicePixelRatio || 1);
    const ch = canvas.height / (window.devicePixelRatio || 1);
    const wx = viewCenter.x - (my - ch / 2) / zoomScale;
    const wy = viewCenter.y - (mx - cw / 2) / zoomScale;
    let closest = null, minD = 99999;
    roomList.forEach((r) => { const d = Math.hypot(r.centerX - wx, r.centerY - wy); if (d < minD) { minD = d; closest = r; } });
    if (closest && minD < 3.5) sendRoomGoal(closest.name);
  };

  const zoomIn = () => setZoomScale((p) => Math.min(60, p * 1.25));
  const zoomOut = () => setZoomScale((p) => Math.max(0.2, p / 1.25));

  /* ════════════════════ JSX ════════════════════ */
  return (
    <div className="min-h-screen flex flex-col bg-[#f5f7fa] text-slate-800 font-sans antialiased">
      {/* ── HEADER ── */}
      <header className="bg-white border-b border-slate-200 px-5 py-2.5 sticky top-0 z-50 flex items-center justify-between gap-4 shadow-sm flex-shrink-0">
        <div className="flex items-center gap-3">
          {/* Brand mark: 38px rounded-lg tile with linear-gradient(135deg, #0D9488, #2563EB) and subtle shadow */}
          <div
            className="w-[38px] h-[38px] rounded-lg flex items-center justify-center shadow-xs flex-shrink-0"
            style={{ background: 'linear-gradient(135deg, #0D9488, #2563EB)' }}
          >
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="white"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 2.5l7 2.8v5.4c0 4.8-3.2 8.6-7 10.8-3.8-2.2-7-6-7-10.8V5.3l7-2.8z" />
              <circle cx="12" cy="10" r="1.9" fill="white" stroke="none" />
              <path d="M12 13.5v2.2M8.6 11.8l-1.7 1.2M15.4 11.8l1.7 1.2M9.3 8l-1.5-1M14.7 8l1.5-1" />
            </svg>
          </div>
          <div>
            <h1 className="text-[15px] font-bold tracking-tight text-slate-900 leading-tight">
              CHIRON-UV
            </h1>
            <p className="text-[11px] text-slate-500 font-medium leading-tight">Autonomous UV-C Disinfection Robot Console</p>
          </div>

          {/* Status pills: 11px semibold, 6px dot */}
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${connected ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-rose-50 text-rose-700 border-rose-200'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-emerald-500' : 'bg-rose-500'}`} />
            {connected ? 'CONNECTED' : 'OFFLINE'}
          </div>

          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${humanDetected ? 'bg-rose-50 text-rose-700 border-rose-200' : disinfectionRunning ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${humanDetected ? 'bg-rose-500' : disinfectionRunning ? 'bg-blue-600' : 'bg-amber-500'}`} />
            {humanDetected ? 'UV BANNED (HUMAN)' : disinfectionRunning ? 'UV ACTIVE' : 'UV STANDBY'}
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Phase chip */}
          <div className="px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200/90 text-[11px] font-semibold flex items-center gap-1.5 text-slate-700 shadow-2xs">
            <Activity className="w-3.5 h-3.5 text-slate-500" strokeWidth={1.75} />
            {roomStatus.phase === 'idle' && <span className="text-slate-500">IDLE</span>}
            {roomStatus.phase === 'transit' && <span className="text-amber-600">TRANSIT → {roomStatus.room} <span className="ml-1 px-1.5 py-0.5 bg-amber-100 text-amber-800 rounded text-[10px] font-bold">~{transitEtaSec}s</span></span>}
            {roomStatus.phase === 'sweeping' && <span className="text-blue-700">SWEEPING {roomStatus.room} ({roomStatus.waypoint}/{roomStatus.total_waypoints})</span>}
            {roomStatus.phase === 'waiting' && <span className="text-emerald-700">DONE ({roomStatus.room})</span>}
            {roomStatus.phase === 'held' && <span className="text-rose-600 font-bold">HELD (HUMAN IN ROOM)</span>}
            {roomStatus.phase === 'stopped' && <span className="text-rose-600 font-bold">STOPPED (E-STOP)</span>}
            {roomStatus.phase === 'paused' && <span className="text-amber-600">PAUSED</span>}
          </div>

          {/* Live Clock */}
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200/90 text-[11px] font-mono font-semibold text-slate-700 shadow-2xs">
            <Clock className="w-3.5 h-3.5 text-slate-500" />
            <span className="tabular-nums tracking-wide">{currentTime}</span>
          </div>

          {/* Operator Chip */}
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200/90 text-[11px] font-semibold text-slate-700 uppercase tracking-wide shadow-2xs">
            <UserCheck className="w-3.5 h-3.5 text-slate-500" />
            <span>Operator</span>
          </div>

          <button
            onClick={() => sendDisinfectionCommand('start')}
            disabled={eStopActive || humanDetected}
            className={`px-3 py-1.5 rounded-lg text-[11px] font-semibold flex items-center gap-1.5 transition-all duration-150 shadow-2xs ${
              humanDetected
                ? 'bg-rose-100 text-rose-600 border border-rose-300 cursor-not-allowed opacity-80'
                : eStopActive
                ? 'bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed opacity-60'
                : disinfectionRunning
                ? 'bg-blue-800 text-blue-100 border border-blue-700 ring-2 ring-blue-500/20 active:scale-[0.98] cursor-pointer'
                : 'bg-gradient-to-b from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white border border-blue-700 hover:shadow-xs active:scale-[0.98] cursor-pointer'
            }`}
            title={humanDetected ? 'UV BANNED: Person detected in room' : 'Start UV Disinfection'}
          >
            <Power className="w-3.5 h-3.5" strokeWidth={2} /> {humanDetected ? 'UV Banned' : 'Start UV'}
          </button>
          <button
            onClick={() => sendDisinfectionCommand('stop')}
            disabled={!disinfectionRunning || eStopActive}
            className={`px-3 py-1.5 rounded-lg text-[11px] font-semibold flex items-center gap-1.5 transition-all duration-150 shadow-2xs ${
              !disinfectionRunning || eStopActive
                ? 'bg-slate-50 text-slate-400 border border-slate-200 cursor-not-allowed opacity-60'
                : 'bg-white hover:bg-slate-50 active:bg-slate-100 text-slate-700 border border-slate-300 hover:shadow-xs active:scale-[0.98] cursor-pointer'
            }`}
          >
            <PowerOff className="w-3.5 h-3.5" strokeWidth={2} /> Stop UV
          </button>
          <button
            onClick={() => sendCommand('estop')}
            className="px-3.5 py-1.5 rounded-lg text-[11px] font-bold tracking-wide uppercase flex items-center gap-1.5 bg-gradient-to-b from-rose-500 to-rose-600 hover:from-rose-600 hover:to-rose-700 active:from-rose-700 active:to-rose-800 text-white border border-rose-600 shadow-2xs hover:shadow-xs active:scale-[0.98] transition-all duration-150 cursor-pointer ring-1 ring-rose-400/20"
          >
            <ShieldAlert className="w-3.5 h-3.5" strokeWidth={2} /> E-Stop
          </button>
        </div>
      </header>

      {/* ── HUMAN DETECTED BANNER ── */}
      {humanDetected && (
        <div className="w-full bg-gradient-to-r from-rose-600 to-rose-700 text-white px-5 py-2.5 text-[11px] font-bold flex items-center justify-between shadow-md flex-shrink-0">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-white animate-pulse" strokeWidth={2} />
            <span>HUMAN DETECTED — UV RADIATION BANNED: Optical safety interlock active. Disinfection halted.</span>
          </div>
          <span className="px-2.5 py-0.5 bg-rose-900/80 border border-rose-400/30 rounded-md font-mono text-[10px]">Persons: {humanCount}</span>
        </div>
      )}

      {eStopActive && (
        <div className="bg-gradient-to-r from-rose-600 to-rose-700 text-white px-5 py-2.5 text-[11px] font-bold flex items-center justify-between shadow-sm flex-shrink-0">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-white" strokeWidth={2} />
            <span>EMERGENCY STOP — Motion paused</span>
          </div>
          <button
            onClick={() => sendCommand('resume')}
            className="px-3 py-1 bg-white hover:bg-rose-50 active:bg-rose-100 text-rose-700 text-[11px] rounded-lg font-bold border border-white/90 shadow-2xs hover:shadow-xs active:scale-[0.98] transition-all duration-150 cursor-pointer"
          >
            Reset
          </button>
        </div>
      )}

      {/* ── MAIN GRID ── */}
      <main className="flex-1 p-5 grid grid-cols-1 lg:grid-cols-12 gap-5 max-w-[1920px] mx-auto w-full">
        {/* ── LEFT COL (8): Metrics → Map → Nav Bar ── */}
        <div className="lg:col-span-8 flex flex-col gap-5">
          {/* Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 flex-shrink-0">
            <div className="bg-white border border-slate-200/90 rounded-xl p-3.5 shadow-2xs hover:shadow-xs transition-shadow">
              <div className="flex items-center justify-between text-slate-500 text-[11px] font-semibold uppercase tracking-wider mb-1.5">
                <span>Coverage</span><Radiation className="w-4 h-4 text-slate-400" strokeWidth={1.75} />
              </div>
              <div className="text-2xl font-bold text-slate-800 tracking-tight">{coveragePct.toFixed(1)}%</div>
              <div className="w-full bg-slate-100 rounded-full h-1.5 mt-2 overflow-hidden">
                <div className="bg-gradient-to-r from-blue-600 to-blue-700 h-1.5 rounded-full transition-all duration-300" style={{ width: `${Math.min(100, coveragePct)}%` }} />
              </div>
            </div>

            <div className="bg-white border border-slate-200/90 rounded-xl p-3.5 shadow-2xs hover:shadow-xs transition-shadow">
              <div className="flex items-center justify-between text-slate-500 text-[11px] font-semibold uppercase tracking-wider mb-1.5">
                <span>Target</span><MapPin className="w-4 h-4 text-slate-400" strokeWidth={1.75} />
              </div>
              <div className="text-xl font-bold text-slate-800 truncate tracking-tight">{roomStatus.room}</div>
              <div className="text-[11px] text-blue-600 font-semibold mt-1">
                {roomStatus.total_waypoints > 0 ? `Waypoint ${roomStatus.waypoint}/${roomStatus.total_waypoints} (${(roomStatus.progress * 100).toFixed(0)}%)` : `Progress: ${(roomStatus.progress * 100).toFixed(0)}%`}
              </div>
            </div>

            <div className="bg-white border border-slate-200/90 rounded-xl p-3.5 shadow-2xs hover:shadow-xs transition-shadow">
              <div className="flex items-center justify-between text-slate-500 text-[11px] font-semibold uppercase tracking-wider mb-1.5">
                <span>Velocity</span><Gauge className="w-4 h-4 text-slate-400" strokeWidth={1.75} />
              </div>
              <div className="text-2xl font-bold text-slate-800 tracking-tight">{odomVel.toFixed(2)} <span className="text-xs font-normal text-slate-400">m/s</span></div>
              <div className="text-[11px] text-slate-400 font-mono mt-1">({robotPose.x.toFixed(1)}, {robotPose.y.toFixed(1)}) {(robotPose.yaw * 180 / Math.PI).toFixed(0)}°</div>
            </div>

            <div className="bg-white border border-slate-200/90 rounded-xl p-3.5 shadow-2xs hover:shadow-xs transition-shadow">
              <div className="flex items-center justify-between text-slate-500 text-[11px] font-semibold uppercase tracking-wider mb-1.5">
                <span>Battery</span><BatteryMedium className="w-4 h-4 text-slate-400" strokeWidth={1.75} />
              </div>
              <div className="text-2xl font-bold text-slate-800 tracking-tight">{batteryState}%</div>
              <div className="w-full bg-slate-100 rounded-full h-1.5 mt-2 overflow-hidden">
                <div className="bg-gradient-to-r from-emerald-500 to-emerald-600 h-1.5 rounded-full w-full" />
              </div>
            </div>
          </div>

          {/* MAP CARD — full width, tall */}
          <div className="bg-white border border-slate-200/90 rounded-xl p-4 flex flex-col shadow-2xs" style={{ height: 'calc(100vh - 300px)', minHeight: '520px' }}>
            <div className="flex items-center justify-between mb-3 flex-shrink-0">
              <div className="flex items-center gap-2">
                <Map className="w-4 h-4 text-slate-500" strokeWidth={1.75} />
                <h2 className="text-sm font-semibold text-slate-800 tracking-tight">Hospital Facility Plan</h2>
              </div>
              <div className="flex items-center gap-3 text-[11px] text-slate-500 font-medium">
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-blue-600 inline-block shadow-2xs" /> Robot</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-orange-500 inline-block shadow-2xs" /> Dose</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-600 inline-block shadow-2xs" /> Done</span>
              </div>
            </div>

            <div className="relative flex-1 bg-[#f1f5f9] rounded-lg overflow-hidden border border-slate-200 select-none min-h-0">
              {/* Map Floating Toolbar */}
              <div className="absolute top-3 right-3 flex items-center gap-1 bg-white/95 border border-slate-200/90 backdrop-blur-md px-1.5 py-1 rounded-lg text-xs shadow-xs z-10">
                <button
                  onClick={zoomIn}
                  className="p-1 hover:bg-slate-100 active:bg-slate-200 text-slate-600 rounded-md transition-colors duration-100 cursor-pointer"
                  title="Zoom In"
                >
                  <Plus className="w-3.5 h-3.5" strokeWidth={2} />
                </button>
                <button
                  onClick={zoomOut}
                  className="p-1 hover:bg-slate-100 active:bg-slate-200 text-slate-600 rounded-md transition-colors duration-100 cursor-pointer"
                  title="Zoom Out"
                >
                  <Minus className="w-3.5 h-3.5" strokeWidth={2} />
                </button>
                <div className="w-[1px] h-3.5 bg-slate-200 mx-0.5" />
                <button
                  onClick={resetFit}
                  className="px-2 py-0.5 hover:bg-slate-100 active:bg-slate-200 text-slate-700 rounded-md text-[11px] font-semibold tracking-tight transition-colors duration-100 flex items-center gap-1 cursor-pointer"
                  title="Fit Map to View"
                >
                  <Maximize2 className="w-3 h-3" strokeWidth={2} /> FIT
                </button>
                <span className="font-mono text-slate-400 text-[10px] px-1">{Math.round((zoomScale / (initialFitRef.current.scale || 8)) * 100)}%</span>
              </div>

              <canvas ref={mapCanvasRef} className="absolute inset-0 w-full h-full cursor-grab active:cursor-grabbing"
                onMouseDown={handleMouseDown} onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp}
                onDoubleClick={handleDoubleClick} onClick={handleCanvasClick}
              />
            </div>
          </div>

          {/* Nav Controls Bar */}
          <div className="bg-white border border-slate-200/90 rounded-xl p-3 shadow-2xs flex items-center justify-between gap-3 flex-shrink-0">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider pl-1.5">
              {eStopActive ? 'Navigation (Locked by E-Stop)' : 'Navigation Controls'}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => sendCommand('start_tour')}
                disabled={eStopActive}
                className={`px-4 py-2 text-white font-semibold rounded-lg text-[11px] flex items-center gap-2 border shadow-2xs transition-all duration-150 ${
                  eStopActive
                    ? 'bg-slate-300 border-slate-300 cursor-not-allowed opacity-60'
                    : 'bg-gradient-to-b from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 active:from-blue-800 active:to-blue-900 border-blue-700 hover:shadow-xs active:scale-[0.98] cursor-pointer'
                }`}
              >
                <Play className="w-3.5 h-3.5 fill-white" /> Start Tour
              </button>
              <button
                onClick={() => sendCommand('pause')}
                disabled={eStopActive}
                className={`px-4 py-2 text-white font-semibold rounded-lg text-[11px] flex items-center gap-2 border shadow-2xs transition-all duration-150 ${
                  eStopActive
                    ? 'bg-slate-300 border-slate-300 cursor-not-allowed opacity-60'
                    : 'bg-gradient-to-b from-amber-400 to-amber-500 hover:from-amber-500 hover:to-amber-600 active:from-amber-600 active:to-amber-700 border-amber-500 hover:shadow-xs active:scale-[0.98] cursor-pointer'
                }`}
              >
                <Pause className="w-3.5 h-3.5 fill-white" /> Pause
              </button>
              <button
                onClick={() => sendCommand('resume')}
                disabled={eStopActive}
                className={`px-4 py-2 text-white font-semibold rounded-lg text-[11px] flex items-center gap-2 border shadow-2xs transition-all duration-150 ${
                  eStopActive
                    ? 'bg-slate-300 border-slate-300 cursor-not-allowed opacity-60'
                    : 'bg-gradient-to-b from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 active:from-blue-800 active:to-blue-900 border-blue-700 hover:shadow-xs active:scale-[0.98] cursor-pointer'
                }`}
                title="Resume paused navigation"
              >
                <Play className="w-3.5 h-3.5 fill-white" /> Resume
              </button>
              <button
                onClick={() => sendCommand('return_home')}
                disabled={eStopActive}
                className={`px-4 py-2 text-white font-semibold rounded-lg text-[11px] flex items-center gap-2 border shadow-2xs transition-all duration-150 ${
                  eStopActive
                    ? 'bg-slate-300 border-slate-300 cursor-not-allowed opacity-60'
                    : 'bg-gradient-to-b from-slate-700 to-slate-800 hover:from-slate-800 hover:to-slate-900 active:from-slate-900 active:to-slate-950 border-slate-700 hover:shadow-xs active:scale-[0.98] cursor-pointer'
                }`}
              >
                <Home className="w-3.5 h-3.5" strokeWidth={2} /> Return Home
                <span className="text-[10px] text-slate-300 font-mono font-normal">{homePose ? `(${homePose.x.toFixed(1)}, ${homePose.y.toFixed(1)})` : ''}</span>
              </button>
            </div>
          </div>
        </div>

        {/* ── RIGHT COL (4): Camera → Rooms → Telemetry → Log ── */}
        <div className="lg:col-span-4 flex flex-col gap-5">
          {/* CAMERA (420px height) */}
          <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-[0_1px_3px_rgba(0,0,0,0.06)] flex flex-col" style={{ height: '420px' }}>
            <div className="flex items-center justify-between mb-2.5 flex-shrink-0">
              <div className="flex items-center gap-2">
                <Video className="w-4 h-4 text-slate-500" strokeWidth={1.75} />
                <h2 className="text-sm font-semibold text-slate-800">Live Camera</h2>
              </div>
              {humanDetected ? (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-100 text-rose-700 border border-rose-200">
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-500" /> HUMAN ({humanCount})
                </span>
              ) : (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> CLEAR
                </span>
              )}
            </div>
            <div className="relative flex-1 bg-[#1e293b] rounded-lg overflow-hidden border border-slate-200 min-h-0">
              {cameraConnected ? (
                <img src="http://localhost:8080/stream?topic=/rs_color/image_raw&width=640" alt="Robot Camera"
                  className="absolute inset-0 w-full h-full object-contain"
                  onError={() => setCameraConnected(false)}
                />
              ) : (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400">
                  <Camera className="w-6 h-6 mb-1.5 text-slate-500" strokeWidth={1.75} />
                  <p className="text-[11px] font-medium text-slate-400">Video Stream Offline</p>
                  <button
                    onClick={() => setCameraConnected(true)}
                    className="mt-2.5 px-3 py-1 bg-slate-700 hover:bg-slate-600 active:bg-slate-800 text-slate-200 font-semibold rounded-lg text-[11px] transition-all shadow-2xs active:scale-[0.98] border border-slate-600/70 cursor-pointer"
                  >
                    Retry Stream
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* ROOMS */}
          <div className="bg-white border border-slate-200/90 rounded-xl p-3.5 shadow-2xs flex flex-col">
            <div className="flex items-center justify-between mb-2.5">
              <div className="flex items-center gap-2">
                <DoorOpen className="w-4 h-4 text-slate-500" strokeWidth={1.75} />
                <h2 className="text-sm font-semibold text-slate-800 tracking-tight">Facility Rooms ({roomList.length})</h2>
              </div>
              {eStopActive ? (
                <span className="text-[11px] text-rose-600 font-bold">LOCKED (E-Stop Active)</span>
              ) : (
                <span className="text-[11px] text-slate-400 font-medium">Click room to dispatch</span>
              )}
            </div>
            <div className="space-y-1.5 max-h-[260px] overflow-y-auto pr-1">
              {roomList.length === 0 ? (
                <div className="text-slate-400 text-center py-4 text-[11px]">Loading facility rooms…</div>
              ) : roomList.map((rm) => {
                const status = roomCompletion[rm.name] || 'pending';
                const isCurrent = roomStatus.room === rm.name;
                const stats = roomStats[rm.name] || { coverage: 0, lastTime: null };
                return (
                  <div
                    key={rm.name}
                    onClick={() => sendRoomGoal(rm.name)}
                    className={`p-2.5 rounded-xl border transition-all duration-150 flex items-center justify-between shadow-2xs ${
                      eStopActive
                        ? 'bg-slate-50/70 border-slate-200 text-slate-400 opacity-60 cursor-not-allowed'
                        : isCurrent && roomStatus.phase === 'held'
                        ? 'bg-rose-50/90 border-rose-300 ring-1 ring-rose-400/20 cursor-pointer active:scale-[0.99]'
                        : isCurrent
                        ? 'bg-blue-50/90 border-blue-300 ring-1 ring-blue-400/20 cursor-pointer active:scale-[0.99]'
                        : status === 'waiting'
                        ? 'bg-emerald-50/50 border-emerald-200/90 hover:border-emerald-300 hover:bg-emerald-50/80 cursor-pointer active:scale-[0.99]'
                        : 'bg-white border-slate-200/80 hover:border-slate-300 hover:bg-slate-50/90 cursor-pointer active:scale-[0.99]'
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <div className="w-2.5 h-2.5 rounded-full flex-shrink-0 shadow-2xs" style={{ backgroundColor: rm.color }} />
                      <div>
                        <div className="text-[11px] font-bold text-slate-800 tracking-tight">{rm.name}</div>
                        <div className="text-[10px] text-slate-400">({rm.centerX.toFixed(1)}, {rm.centerY.toFixed(1)}) · {stats.lastTime || '—'}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-semibold bg-blue-50 text-blue-700 border border-blue-200/80">
                        {stats.coverage > 0 ? `${stats.coverage}%` : isCurrent ? `${Math.round(roomStatus.progress * 100)}%` : '0%'}
                      </span>
                      {isCurrent && roomStatus.phase === 'held' ? (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-600 text-white shadow-2xs">
                          <AlertTriangle className="w-3 h-3 text-white animate-pulse" /> held
                        </span>
                      ) : isCurrent ? (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-600 text-white shadow-2xs">
                          <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" /> {roomStatus.phase === 'transit' ? 'transit' : 'sweeping'} ({roomStatus.waypoint}/{roomStatus.total_waypoints})
                        </span>
                      ) : status === 'waiting' ? (
                        <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-700 border border-emerald-200/60">
                          <Check className="w-3 h-3 text-emerald-600" strokeWidth={2.5} /> done
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-500 border border-slate-200/60 group-hover:border-slate-300">ready</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* TELEMETRY */}
          <div className="bg-white border border-slate-200/90 rounded-xl p-3.5 shadow-2xs">
            <div className="flex items-center gap-2 mb-2.5">
              <Gauge className="w-4 h-4 text-slate-500" strokeWidth={1.75} />
              <h2 className="text-sm font-semibold text-slate-800 tracking-tight">Sensor & Safety Telemetry</h2>
            </div>
            <div className="grid grid-cols-2 gap-2.5 text-xs">
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200/90 shadow-2xs">
                <span className="text-slate-400 block text-[11px] mb-0.5 font-medium">Min Obstacle</span>
                <span className="text-base font-bold text-slate-800 tracking-tight">{minObstacleDist < 900 ? `${minObstacleDist.toFixed(2)} m` : 'Clear'}</span>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200/90 shadow-2xs">
                <span className="text-slate-400 block text-[11px] mb-0.5 font-medium">Human Safety</span>
                <span className={`text-base font-bold tracking-tight ${humanDetected ? 'text-rose-600' : 'text-emerald-600'}`}>{humanDetected ? `Present (${humanCount})` : 'Clear'}</span>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200/90 shadow-2xs">
                <span className="text-slate-400 block text-[11px] mb-0.5 font-medium">Heading</span>
                <span className="text-base font-bold text-slate-800 tracking-tight">{(robotPose.yaw * 180 / Math.PI).toFixed(1)}°</span>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200/90 shadow-2xs">
                <span className="text-slate-400 block text-[11px] mb-0.5 font-medium">UV Lamp</span>
                <span className={`text-sm font-bold flex items-center gap-1.5 ${humanDetected ? 'text-rose-600' : disinfectionRunning ? 'text-blue-600' : 'text-slate-500'}`}>
                  <Flame className={`w-3.5 h-3.5 ${humanDetected ? 'text-rose-500' : disinfectionRunning ? 'text-blue-600' : 'text-slate-400'}`} strokeWidth={1.75} />
                  {humanDetected ? 'Banned (Safety Lock)' : disinfectionRunning ? 'Active' : 'Standby'}
                </span>
              </div>
            </div>
          </div>

          {/* OPERATION ACTIVITY LOG */}
          <div className="bg-white border border-slate-200/90 rounded-xl p-4 shadow-2xs flex-1 flex flex-col min-h-[220px]">
            {/* Header */}
            <div className="flex items-center justify-between mb-3 flex-shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="p-1.5 bg-slate-100 rounded-lg text-slate-600 border border-slate-200/60 shadow-2xs">
                  <Terminal className="w-4 h-4 text-slate-600" strokeWidth={1.75} />
                </div>
                <h2 className="text-sm font-semibold text-slate-800 tracking-tight">Operation Activity Log</h2>
                <span className="bg-slate-100 text-slate-600 text-[11px] font-semibold px-2 py-0.5 rounded-full font-mono tabular-nums border border-slate-200/60">
                  {logs.length}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setLogs([])}
                  className="flex items-center gap-1.5 text-slate-500 hover:text-slate-700 active:text-slate-900 text-[12px] font-medium transition cursor-pointer px-2 py-1 rounded-md hover:bg-slate-100"
                  title="Clear Activity Log"
                >
                  <Trash2 className="w-3.5 h-3.5 text-slate-500" strokeWidth={1.75} />
                  <span>Clear</span>
                </button>
                <button
                  onClick={() => setLogExpanded(!logExpanded)}
                  className="p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition cursor-pointer"
                  title={logExpanded ? 'Collapse Log' : 'Expand Log'}
                >
                  {logExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {logExpanded && (
              <>
                {/* Filter Tab Row */}
                <div className="flex items-center gap-1 p-1 bg-slate-100/80 rounded-lg border border-slate-200/60 mb-3 flex-shrink-0 overflow-x-auto">
                  {[
                    { id: 'all', label: 'All', count: logs.length },
                    { id: 'success', label: 'Success', count: logs.filter((l) => l.type === 'success').length },
                    { id: 'info', label: 'Info', count: logs.filter((l) => l.type === 'info').length },
                    { id: 'warning', label: 'Warning', count: logs.filter((l) => l.type === 'warning').length },
                    { id: 'error', label: 'Error', count: logs.filter((l) => l.type === 'error').length },
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setLogFilter(tab.id)}
                      className={`px-2.5 py-1 rounded-md text-[11px] transition-all flex items-center gap-1 cursor-pointer flex-shrink-0 ${
                        logFilter === tab.id
                          ? 'bg-white border border-slate-200/90 shadow-2xs text-slate-800 font-semibold'
                          : 'text-slate-500 hover:text-slate-700 hover:bg-white/60 font-medium'
                      }`}
                    >
                      <span>{tab.label}</span>
                      <span className={`text-[10px] font-mono tabular-nums px-1 rounded ${logFilter === tab.id ? 'bg-slate-100 text-slate-700 font-semibold' : 'text-slate-400'}`}>
                        {tab.count}
                      </span>
                    </button>
                  ))}
                </div>

                {/* Entries List */}
                <div className="flex-1 overflow-y-auto max-h-[300px] thin-scrollbar space-y-2.5 pr-1">
                  {logs.filter((l) => logFilter === 'all' || l.type === logFilter).length === 0 ? (
                    <div className="text-slate-400 text-center py-6 text-[12px] font-medium">
                      {logs.length === 0 ? 'No activity events recorded.' : `No events matching "${logFilter}".`}
                    </div>
                  ) : (
                    logs
                      .filter((l) => logFilter === 'all' || l.type === logFilter)
                      .map((log) => {
                        const isSuccess = log.type === 'success';
                        const isInfo = log.type === 'info';
                        const isWarning = log.type === 'warning';
                        const isError = log.type === 'error';

                        return (
                          <div key={log.id} className="border-b border-slate-100 pb-2.5 last:border-b-0 last:pb-0">
                            <div className="flex items-start gap-2.5">
                              {/* Left Icon in Colored Circle */}
                              <div className="mt-0.5 flex-shrink-0">
                                {isSuccess && (
                                  <div className="p-1 bg-emerald-50 border border-emerald-200/60 rounded-full">
                                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" strokeWidth={2} />
                                  </div>
                                )}
                                {isInfo && (
                                  <div className="p-1 bg-blue-50 border border-blue-200/60 rounded-full">
                                    <Info className="w-3.5 h-3.5 text-blue-500" strokeWidth={2} />
                                  </div>
                                )}
                                {isWarning && (
                                  <div className="p-1 bg-amber-50 border border-amber-200/60 rounded-full">
                                    <AlertTriangle className="w-3.5 h-3.5 text-amber-500" strokeWidth={2} />
                                  </div>
                                )}
                                {isError && (
                                  <div className="p-1 bg-rose-50 border border-rose-200/60 rounded-full">
                                    <ShieldAlert className="w-3.5 h-3.5 text-rose-500" strokeWidth={2} />
                                  </div>
                                )}
                              </div>

                              {/* Content: Badge + Timestamp + Message */}
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between gap-2 mb-0.5">
                                  <span
                                    className={`uppercase text-[10px] font-bold px-1.5 py-0.5 rounded tracking-wider ${
                                      isSuccess
                                        ? 'bg-emerald-100 text-emerald-700'
                                        : isInfo
                                        ? 'bg-blue-100 text-blue-700'
                                        : isWarning
                                        ? 'bg-amber-100 text-amber-700'
                                        : 'bg-rose-100 text-rose-700'
                                    }`}
                                  >
                                    {log.type}
                                  </span>
                                  <span className="text-[12px] text-slate-400 font-mono tabular-nums flex-shrink-0">
                                    {log.time}
                                  </span>
                                </div>
                                <p className="text-slate-600 text-[13px] leading-relaxed font-normal">
                                  {log.text}
                                </p>
                              </div>
                            </div>
                          </div>
                        );
                      })
                  )}
                </div>

                {/* Footer Bar */}
                <div className="border-t border-slate-100 pt-2.5 mt-2.5 flex items-center justify-between flex-shrink-0">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse flex-shrink-0" />
                    <span className="text-[12px] text-slate-500 font-medium">Live — Real-time system events</span>
                  </div>
                  <span className="text-[11px] text-slate-400 font-mono tabular-nums">
                    {logs.filter((l) => logFilter === 'all' || l.type === logFilter).length} of {logs.length}
                  </span>
                </div>
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
