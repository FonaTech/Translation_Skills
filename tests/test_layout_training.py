import copy
import sys
import unittest
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import train_layout_model as trainer
try:
    import numpy as np
except ImportError:
    np = None


@unittest.skipIf(np is None, 'NumPy is an optional training dependency')
class LayoutTrainingTests(unittest.TestCase):
    def dataset(self):
        documents = []
        for i in range(8):
            candidates = []
            for j in range(3):
                x = [0.0] * len(trainer.FEATURES)
                x[5] = .45 + j * .1 + i * .005
                x[7] = .3 + j * .12
                x[9] = j * .03
                candidates.append({'candidate': str(j), 'features': x, 'report': {'pages': 2}})
            documents.append({'document': str(i), 'fixture': {}, 'candidates': candidates})
        return {'seed': 173, 'features': trainer.FEATURES, 'documents': documents}

    def test_contraction_matches_scalar_reference_without_warnings(self):
        a = np.array([[.5, -2, 3], [4, 0, -1]], dtype=float)
        b = np.array([[2, -3], [1, 5], [-4, .25]], dtype=float)
        expected = [[sum(a[i, k] * b[k, j] for k in range(3)) for j in range(2)] for i in range(2)]
        with warnings.catch_warnings():
            warnings.simplefilter('error', RuntimeWarning)
            np.testing.assert_allclose(trainer.contract(a, b, np), expected)
            np.testing.assert_allclose(trainer.contract(a, np.array([1., 2., 3.]), np), [5.5, 1.])

    def test_training_is_finite_deterministic_and_has_held_out_documents(self):
        with warnings.catch_warnings():
            warnings.simplefilter('error', RuntimeWarning)
            model, report = trainer.train(self.dataset(), 5)
            repeated, _ = trainer.train(self.dataset(), 5)
        self.assertEqual(model, repeated)
        self.assertEqual(model['training_documents'], 6)
        self.assertEqual(model['holdout_documents'], 2)
        self.assertTrue(np.isfinite(model['weights']).all())
        self.assertEqual(report['numerics']['floating_errors'], 'raise')

    def test_nonfinite_and_wrong_dimensions_are_rejected(self):
        for value in [float('nan'), float('inf'), -float('inf')]:
            data = self.dataset()
            data['documents'][0]['candidates'][0]['features'][0] = value
            with self.assertRaisesRegex(ValueError, 'Non-finite'):
                trainer.train(data, 2)
        data = self.dataset()
        data['documents'][0]['candidates'][0]['features'].pop()
        with self.assertRaisesRegex(ValueError, 'dimensions'):
            trainer.train(data, 2)

    def test_empty_preference_set_is_rejected(self):
        data = self.dataset()
        for document in data['documents']:
            for candidate in document['candidates']:
                candidate['features'] = [0.] * len(trainer.FEATURES)
        with self.assertRaisesRegex(ValueError, 'preference pairs'):
            trainer.train(data, 2)
