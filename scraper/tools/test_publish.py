import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import update_indexes as update


class PublishTests(unittest.TestCase):
    def fixture(self, root):
        formal=root/'formal';batch=root/'batch';candidate=batch/'candidate-final'
        formal.mkdir();candidate.mkdir(parents=True)
        poster=root/'poster.png';poster.write_bytes(b'fixture image bytes')
        files=[f'{name}.{kind}.json' for name in update.NAMES for kind in ('index','report')]
        for name in files:
            update.write(formal/name,{'previous':name})
            item={'recordId':'new','posterPath':str(poster),'posterSha256':update.digest(poster)}
            update.write(candidate/name,{'items':[item]} if '.index.' in name else {'new':name})
        (formal/'README.md').write_text('original docs')
        (formal/'direction_overrides.json').write_text('{"overrides":{}}')
        inputs={name:update.digest(formal/name) for name in files+['direction_overrides.json']}
        update.write(batch/'formal-input-hashes.json',inputs)
        update.write(batch/'acceptance.json',{'valid':True,'visual_reviewed':True,'posters':[]})
        update.write(batch/'index-diff.json',[])
        update.write(batch/'preview-integrity.json',{
            'acceptance_sha256':update.digest(batch/'acceptance.json'),
            'diff_sha256':update.digest(batch/'index-diff.json'),
            'candidate_files':{name:update.digest(candidate/name) for name in files}})
        return formal,batch,files,inputs

    def test_candidate_drift_stops_before_backup_or_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            formal,batch,files,inputs=self.fixture(Path(tmp))
            (batch/'candidate-final'/files[0]).write_text('changed')
            with patch.object(update,'FORMAL',formal),patch.object(update,'BATCH',batch):
                with self.assertRaisesRegex(RuntimeError,'Candidate changed'):update.publish()
            self.assertFalse((formal/'backups').exists())
            self.assertTrue(all(update.digest(formal/name)==value for name,value in inputs.items()))

    def test_replace_failure_restores_already_written_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            formal,batch,files,inputs=self.fixture(Path(tmp));real_replace=update.os.replace;calls=[]
            def fail_once(source,target):
                calls.append(str(target))
                if len(calls)==3:raise OSError('fixture write failure')
                return real_replace(source,target)
            with patch.object(update,'FORMAL',formal),patch.object(update,'BATCH',batch), \
                 patch.object(update.os,'replace',side_effect=fail_once):
                with self.assertRaisesRegex(OSError,'fixture write failure'):update.publish()
            self.assertTrue(all(update.digest(formal/name)==value for name,value in inputs.items()))
            backup=formal/'backups/20261013-index-posters'
            self.assertTrue((backup/'backup-manifest.json').exists())
            self.assertFalse((batch/'formal-readback.json').exists())

    def test_media_check_drift_does_not_overwrite_concurrent_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            formal,batch,files,inputs=self.fixture(Path(tmp));original=update.digest;changed=[]
            def drift_once(path):
                result=original(path)
                if Path(path).name=='poster.png' and not changed:
                    changed.append(True);(formal/files[0]).write_text('concurrent owner edit')
                return result
            with patch.object(update,'FORMAL',formal),patch.object(update,'BATCH',batch),patch.object(update,'digest',side_effect=drift_once):
                with self.assertRaisesRegex(RuntimeError,'during media validation'):update.publish()
            self.assertEqual((formal/files[0]).read_text(),'concurrent owner edit')
            self.assertFalse((formal/'backups').exists())

    def test_staging_disk_full_leaves_all_formal_files_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            formal,batch,files,inputs=self.fixture(Path(tmp));real_fsync=update.os.fsync
            def disk_full(fd):raise OSError('fixture disk full')
            with patch.object(update,'FORMAL',formal),patch.object(update,'BATCH',batch),patch.object(update.os,'fsync',side_effect=disk_full):
                with self.assertRaisesRegex(OSError,'disk full'):update.publish()
            self.assertTrue(all(update.digest(formal/name)==value for name,value in inputs.items()))

    def test_recovery_uses_staged_payload_without_allocating_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            formal,batch,files,inputs=self.fixture(Path(tmp));real_replace=update.os.replace;count=[]
            def fail_once(source,target):
                if str(source).endswith('.20261013.tmp'):
                    count.append(True)
                    if len(count)==3:raise OSError('fixture disk full')
                return real_replace(source,target)
            real_copy=update.shutil.copy2
            def no_copy_after_replace(source,target):
                if count:raise OSError('copy allocation unavailable')
                return real_copy(source,target)
            with patch.object(update,'FORMAL',formal),patch.object(update,'BATCH',batch),patch.object(update.os,'replace',side_effect=fail_once),patch.object(update.shutil,'copy2',side_effect=no_copy_after_replace):
                with self.assertRaisesRegex(OSError,'disk full'):update.publish()
            self.assertTrue(all(update.digest(formal/name)==value for name,value in inputs.items()))


if __name__=='__main__':unittest.main()
