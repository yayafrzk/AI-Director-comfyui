import asyncio
from pathlib import Path

import app.services.generation_archive as archive
from app.db.init_db import init_db
from app.db.session import create_engine_for_path, create_session_factory
from app.models.asset import Asset
from app.models.generation_job import GenerationJob
from app.models.generation_output import GenerationOutput
from app.models.project import Project
from app.models.scene import Scene
from app.models.workflow_template import WorkflowTemplate


def _job(factory):
    with factory() as s:
        p=Project(name="Archive",description=None,aspect_ratio="16:9",width=1,height=1,fps=24);s.add(p);s.commit()
        scene=Scene(project_id=p.id,scene_number=1,title="s",description=None,prompt="p",negative_prompt=None,seed=None,duration_seconds=1,workflow_template_id=None,selected_asset_id=None,status="draft")
        workflow=WorkflowTemplate(name="archive",slug="archive",version="1",template_path="x",manifest_path="y");s.add_all([scene,workflow]);s.commit()
        job=GenerationJob(project_id=p.id,scene_id=scene.id,workflow_template_id=workflow.id,workflow_version="1",prompt_snapshot="p",negative_prompt_snapshot=None,seed=None,params_json={},comfy_prompt_id="prompt-1",status="running");s.add(job);s.commit();return job.id,p.id


def test_archive_image_multiple_and_idempotent(tmp_path,monkeypatch):
    engine=create_engine_for_path(tmp_path/'db.sqlite');init_db(engine);factory=create_session_factory(engine);monkeypatch.setattr(archive,'SessionLocal',factory);monkeypatch.setattr(archive,'asset_directory',lambda project,typ: tmp_path/'projects'/project/('images' if typ=='image' else 'videos'))
    history={"prompt-1":{"outputs":{"2":{"images":[{"filename":"中文.png","subfolder":"","type":"output"},{"filename":"中文.png","subfolder":"","type":"output"}]},"1":{"videos":[{"filename":"clip.mp4","subfolder":"","type":"output"}]}}}}
    monkeypatch.setattr(archive,'get_history',lambda _: asyncio.sleep(0,result=history));monkeypatch.setattr(archive,'download_output',lambda *args: asyncio.sleep(0,result=b'x'))
    try:
        job_id,project_id=_job(factory);assert asyncio.run(archive.archive_generation(job_id))["type"]=="generation.completed";assert asyncio.run(archive.archive_generation(job_id))["type"]=="generation.completed"
        with factory() as s:
            job=s.get(GenerationJob,job_id);outputs=s.query(GenerationOutput).filter_by(generation_job_id=job_id).order_by(GenerationOutput.output_index).all();assets=s.query(Asset).all()
            assert job.status=='completed' and [o.output_index for o in outputs]==[0,1,2] and len(assets)==3 and all(not Path(a.relative_path).is_absolute() for a in assets)
            assert len({a.relative_path for a in assets})==3 and {a.type for a in assets}=={'image','video'}
    finally: engine.dispose()


def test_archive_no_output_and_unsafe_path_fail(tmp_path,monkeypatch):
    engine=create_engine_for_path(tmp_path/'db.sqlite');init_db(engine);factory=create_session_factory(engine);monkeypatch.setattr(archive,'SessionLocal',factory);monkeypatch.setattr(archive,'get_history',lambda _: asyncio.sleep(0,result={"prompt-1":{"outputs":{}}}))
    try:
        job_id,_=_job(factory);result=asyncio.run(archive.archive_generation(job_id));
        with factory() as s: assert result['type']=='generation.failed' and s.get(GenerationJob,job_id).error_code=='OUTPUT_NOT_FOUND' and s.query(Asset).count()==0
    finally: engine.dispose()


def test_archive_download_failure_cleans_database_and_files(tmp_path, monkeypatch):
    engine=create_engine_for_path(tmp_path/'fail.db');init_db(engine);factory=create_session_factory(engine);monkeypatch.setattr(archive,'SessionLocal',factory);root=tmp_path/'projects';monkeypatch.setattr(archive,'asset_directory',lambda project,typ: root/project/('videos' if typ=='video' else 'images'))
    history={"prompt-1":{"outputs":{"2":{"videos":[{"filename":"one.mp4","subfolder":"","type":"output"},{"filename":"two.mp4","subfolder":"","type":"output"}]}}}}
    monkeypatch.setattr(archive,'get_history',lambda _: asyncio.sleep(0,result=history));calls=[]
    async def download(*_):
        calls.append(1)
        if len(calls)==2: raise archive.ComfyUIClientError('COMFYUI_SUBMIT_FAILED','download failed')
        return b'ok'
    monkeypatch.setattr(archive,'download_output',download)
    try:
        job_id,project_id=_job(factory);result=asyncio.run(archive.archive_generation(job_id))
        with factory() as s: assert result['type']=='generation.failed' and s.get(GenerationJob,job_id).status=='failed' and s.query(Asset).count()==0 and s.query(GenerationOutput).count()==0
        assert not [path for path in (root/project_id).rglob('*') if path.is_file()]
    finally: engine.dispose()


import pytest
@pytest.mark.parametrize('filename,subfolder',[('../evil.mp4',''),('..\\evil.mp4',''),('C:\\evil.mp4',''),('/evil.mp4',''),('ok.mp4','../../outside')])
def test_archive_rejects_unsafe_history_paths(tmp_path,monkeypatch,filename,subfolder):
    engine=create_engine_for_path(tmp_path/'unsafe.db');init_db(engine);factory=create_session_factory(engine);monkeypatch.setattr(archive,'SessionLocal',factory);monkeypatch.setattr(archive,'asset_directory',lambda project,typ: tmp_path/'projects'/project/'videos')
    monkeypatch.setattr(archive,'get_history',lambda _: asyncio.sleep(0,result={"prompt-1":{"outputs":{"1":{"videos":[{"filename":filename,"subfolder":subfolder,"type":"output"}]}}}}))
    try:
        job_id,_=_job(factory);result=asyncio.run(archive.archive_generation(job_id))
        with factory() as s: assert result['type']=='generation.failed' and s.query(Asset).count()==0 and s.query(GenerationOutput).count()==0
    finally: engine.dispose()


def test_archive_numeric_node_order_and_history_failure(tmp_path,monkeypatch):
    engine=create_engine_for_path(tmp_path/'order.db');init_db(engine);factory=create_session_factory(engine);monkeypatch.setattr(archive,'SessionLocal',factory);monkeypatch.setattr(archive,'asset_directory',lambda project,typ: tmp_path/'projects'/project/'images')
    history={"prompt-1":{"outputs":{"10":{"images":[{"filename":"ten.png","subfolder":"","type":"output"}]},"2":{"images":[{"filename":"two.png","subfolder":"","type":"output"}]}}}}
    monkeypatch.setattr(archive,'get_history',lambda _: asyncio.sleep(0,result=history));downloaded=[]
    async def download(name,*_): downloaded.append(name); return b'x'
    monkeypatch.setattr(archive,'download_output',download)
    try:
        job_id,_=_job(factory);asyncio.run(archive.archive_generation(job_id));assert downloaded==['two.png','ten.png'];assert len(downloaded)==2;asyncio.run(archive.archive_generation(job_id));assert len(downloaded)==2
    finally: engine.dispose()



def test_archive_history_failure_marks_job_failed(tmp_path, monkeypatch):
    engine=create_engine_for_path(tmp_path/'history-fail.db');init_db(engine);factory=create_session_factory(engine);monkeypatch.setattr(archive,'SessionLocal',factory)
    async def fail(_): raise archive.ComfyUIClientError('COMFYUI_TIMEOUT','history failed')
    monkeypatch.setattr(archive,'get_history',fail)
    try:
        job_id,_=_job(factory);result=asyncio.run(archive.archive_generation(job_id))
        with factory() as s: assert result['type']=='generation.failed' and s.get(GenerationJob,job_id).status=='failed' and s.query(Asset).count()==0 and s.query(GenerationOutput).count()==0
    finally: engine.dispose()
