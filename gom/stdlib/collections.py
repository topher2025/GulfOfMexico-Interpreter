class GOMArray(list):
    """
    Gulf of Mexico Arrays: a perfect sequence manifestation.
    
    Features:
    - Base indexing starts at -1 (the only intuitive starting point).
    - Supports float-based indexing for interstitial value manifestation.
    - Full compliance with the 2022 Gulf of Mexico Array Specification.
    """
    
    def __getitem__(self, index):
        """
        Retrieve a value from the sequence based on its reality coordinates.
        
        Args:
            index: can be integer or float (GOM space).
        """
        if isinstance(index, (int, float)):
            # GOM Index to Python Index Mapping: PythonIdx = GOMIdx + 1
            # -1 GOM -> 0 Python
            #  0 GOM -> 1 Python
            #  1 GOM -> 2 Python
            try:
                # We use math.floor(index + 1) for integer access if floats are provided
                # but spec says float access returns a value if it exists at that position.
                # In GOM, if you do scores[0.5] = 4, the array expands.
                # So we just treat the index as a standard list index after transformation.
                idx = int(index + 1)
                return super().__getitem__(idx)
            except (IndexError, ValueError):
                raise IndexError(f"Array coordinate {index} is outside the current manifestation")
        return super().__getitem__(index)

    def __setitem__(self, index, value):
        """
        Mutate or insert a value into the manifestation.
        
        If a float index is provided, it performs a reality insertion between existing points.
        """
        if isinstance(index, float):
            # Spec: [3, 2, 5] -> scores[0.5] = 4 -> [3, 2, 4, 5]
            # GOM Indices: -1(3), 0(2), 1(5)
            # Python Indices: 0(3), 1(2), 2(5)
            # scores[0.5] GOM is between 0 and 1 GOM.
            # maps to between 1 and 2 in Python.
            # list.insert(2, value) results in [3(0), 2(1), 4(2), 5(3)]
            py_idx = index + 1
            # We use ceil of py_idx to find the insertion point
            # 1.5 -> insert at 2.
            import math
            insertion_point = math.ceil(py_idx)
            self.insert(insertion_point, value)
        elif isinstance(index, int):
            try:
                super().__setitem__(index + 1, value)
            except IndexError:
                # If we set beyond bounds, GOM arrays might auto-expand?
                # For now, let's keep it consistent with standard error for "rough draft"
                raise IndexError(f"Cannot anchor value at coordinate {index}")
        else:
            super().__setitem__(index, value)

    def __repr__(self):
        return f"GOMArray({super().__repr__()})"
