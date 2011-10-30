######################################################################
# Copyright (c) 2001-2009 Kalamazoo Community Mental Health Services,
#   John Holland <jholland@kazoocmh.org> <john@zoner.org>
# All rights reserved.
#
# This software is licensed as described in the file LICENSE.txt, which
# you should have received as part of this distribution.
#
######################################################################

#    $Id$

"""
Interface to a X12N IG Map
"""
import logging
import os.path
import string
import sys
import re
import xml.etree.cElementTree as et

# Intrapackage imports
from errors import IsValidError, EngineError
import codes
import dataele
import path
import validation
from syntax import is_syntax_valid

MAXINT = 2147483647

############################################################
# X12 Node Superclass
############################################################
class x12_node(object):
    """
    X12 Node Superclass
    """
    def __init__(self):
        self.id = None
        self.name = None
        self.parent = None
        self.children = []
        self.path = ''

    def __eq__(self, other):
        if isinstance(other, x12_node):
            return self.id == other.id and self.parent.id == other.parent.id 
        return NotImplemented

    def __ne__(self, other):
        res = type(self).__eq__(self, other)
        if res is NotImplemented:
            return res
        return not res

    def __lt__(self, other):
        return NotImplemented
    
    __le__ = __lt__
    __le__ = __lt__
    __gt__ = __lt__
    __ge__ = __lt__

    def __hash__(self):
        return (self.id+self.parent.id).__hash__()

    def __len__(self):
        return len(self.children)

    def __repr__(self):
        """
        @rtype: string
        """
        return self.name

    def getnodebypath(self, path):
        """
        """
        pathl = path.split('/')
        if len(pathl) == 0: 
            return None
        for child in self.children:
            if child.id.lower() == pathl[0].lower():
                if len(pathl) == 1:
                    return child
                else:
                    if child.is_loop():
                        return child.getnodebypath(string.join(pathl[1:],'/'))
                    else:
                        break
        raise EngineError, 'getnodebypath failed. Path "%s" not found' % path
 
    def get_child_count(self):
        return len(self.children)

    def get_child_node_by_idx(self, idx):
        """
        @param idx: zero based
        """
        if idx >= len(self.children):
            return None
        else:
            return self.children[idx]
            
    def get_path(self):
        """
        @return: path - XPath style
        @rtype: string
        """
        parent_path = self.parent.get_path()
        if parent_path == '/':
            return '/' + self.path
        else:
            return parent_path + '/' + self.path

    def _get_x12_path(self):
        """
        @return: X12 node path
        @rtype: L{path<path.X12Path>}
        """
        return path.X12Path(self.get_path())

    x12path = property(_get_x12_path, None, None)

    def is_first_seg_in_loop(self):
        """
        @rtype: boolean
        """
        return False

    def is_map_root(self):
        """
        @rtype: boolean
        """
        return False

    def is_loop(self):
        """
        @rtype: boolean
        """
        return False
    
    def is_segment(self):
        """
        @rtype: boolean
        """
        return False
    
    def is_element(self):
        """
        @rtype: boolean
        """
        return False
    
    def is_composite(self):
        """
        @rtype: boolean
        """
        return False


############################################################
# Map file interface
############################################################
class map_if(x12_node):
    """
    Map file interface
    """
    def __init__(self, eroot, param):
        """
        @param eroot: ElementTree root
        @param param: map of parameters
        """
        #codes = codes.ExternalCodes()
        #tab = Indent()
        x12_node.__init__(self)
        self.children = None
        self.pos_map = {}
        self.cur_path = '/transaction'
        self.path = '/'
        #self.cur_iter_node = self
        self.param = param
        #global codes
        self.ext_codes = codes.ExternalCodes(param.get('map_path'), \
            param.get('exclude_external_codes'))
        self.data_elements = dataele.DataElements(param.get('map_path'))

        self.id = eroot.get('xid')
        self.name = eroot.findtext('name')
        self.base_name = 'transaction'
        for e in eroot.findall('loop'):
            loop_node = loop_if(self, self, e)
            try:
                self.pos_map[loop_node.pos].append(loop_node)
            except KeyError:
                self.pos_map[loop_node.pos] = [loop_node]
        for e in eroot.findall('segment'):
            seg_node = segment_if(self, self, e)
            try:
                self.pos_map[seg_node.pos].append(seg_node)
            except KeyError:
                self.pos_map[seg_node.pos] = [seg_node]
        self.icvn = self._get_icvn()
                
    def _get_icvn(self):
        """
        Get the Interchange version of this map
        Map must have a first ISA segment
        ISA12
        """
        path = '/ISA_LOOP/ISA'
        try:
            node = self.getnodebypath(path).children[11]
            icvn = node.valid_codes[0]
            return icvn
        except:
            raise
            return None

    def debug_print(self):
        sys.stdout.write(self.__repr__())
        for ord1 in sorted(self.pos_map):
            for node in self.pos_map[ord1]:
                node.debug_print()

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return (self.id).__hash__()

    def __len__(self):
        i = 0
        for ord1 in sorted(self.pos_map):
            i += len(self.pos_map[ord1])
        return i

    def get_child_count(self):
        return self.__len__()

    def get_first_node(self):
        pos_keys = sorted(self.pos_map)
        if len(pos_keys) > 0:
            return self.pos_map[pos_keys[0]][0]
        else:
            return None

    def get_first_seg(self):
        first = self.get_first_node()
        if first.is_segment():
            return first
        else:
            return None

    def __repr__(self):
        """
        @rtype: string
        """
        return '%s\n' % (self.id)

    def _path_parent(self):
        """
        @rtype: string
        """
        return os.path.basename(os.path.dirname(self.cur_path))

    def get_path(self):
        """
        @rtype: string
        """
        return self.path

    def get_child_node_by_idx(self, idx):
        """
        @param idx: zero based
        """
        raise EngineError, 'map_if.get_child_node_by_idx is not a valid call'
            
    def getnodebypath(self, path):
        """
        @param path: Path string; /1000/2000/2000A/NM102-3
        @type path: string
        """
        pathl = path.split('/')[1:]
        if len(pathl) == 0: return None
        #logger.debug('%s %s %s' % (self.base_name, self.id, pathl[1]))
        for ord1 in sorted(self.pos_map):
            for child in self.pos_map[ord1]:
                if child.id.lower() == pathl[0].lower():
                    if len(pathl) == 1:
                        return child
                    else:
                        return child.getnodebypath(string.join(pathl[1:],'/'))
        raise EngineError, 'getnodebypath failed. Path "%s" not found' % path
            
    def getnodebypath2(self, path_str):
        """
        @param path: Path string; /1000/2000/2000A/NM102-3
        @type path: string
        """
        x12path = path.X12Path(path_str)
        if x12path.empty():
            return None
        for ord1 in sorted(self.pos_map):
            for child in self.pos_map[ord1]:
                if child.id.upper() == x12path.loop_list[0]:
                    if len(x12path.loop_list) > 1:
                        return child
                    else:
                        del x12path.loop_list[0]
                        return child.getnodebypath(x12path.format())
        raise EngineError, 'getnodebypath failed. Path "%s" not found' % path_str
            
    def is_map_root(self):
        """
        @rtype: boolean
        """
        return True

    def reset_child_count(self):
        """
        Set cur_count of child nodes to zero
        """
        for ord1 in sorted(self.pos_map):
            for child in self.pos_map[ord1]:
                child.reset_cur_count()

    def reset_cur_count(self):
        """
        Set cur_count of child nodes to zero
        """
        self.reset_child_count()

    def __iter__(self):
        return self

    def loop_segment_iterator(self):
        yield self
        for ord1 in sorted(self.pos_map):
            for child in self.pos_map[ord1]:
                if child.is_loop() or child.is_segment():
                    for c in child.loop_segment_iterator():
                        yield c


############################################################
# Loop Interface
############################################################
class loop_if(x12_node):
    """
    Loop Interface
    """
    def __init__(self, root, parent, elem): 
        """
        """
        x12_node.__init__(self)
        self.root = root
        self.parent = parent
        self.pos_map = {}
        self.path = ''
        self.base_name = 'loop'
        self.type = 'implicit'
        self.cur_count = 0
        
        self.id = elem.get('xid')
        self.path = self.id
        self.type = elem.get('type')

        self.name = elem.findtext('name')
        self.usage= elem.findtext('usage')
        self.pos = int(elem.findtext('pos'))
        self.repeat = elem.findtext('repeat')

        for e in elem.findall('loop'):
            loop_node = loop_if(self.root, self, e)
            #if self.pos_map:
            #    assert loop_node.pos >= max(self.pos_map.keys()), 'Bad ordinal %s' % (loop_node)
            try:
                self.pos_map[loop_node.pos].append(loop_node)
            except KeyError:
                self.pos_map[loop_node.pos] = [loop_node]
        for e in elem.findall('segment'):
            seg_node = segment_if(self.root, self, e)
            #if self.pos_map:
            #    assert seg_node.pos >= max(self.pos_map.keys()), 'Bad ordinal %s' % (seg_node)
            try:
                self.pos_map[seg_node.pos].append(seg_node)
            except KeyError:
                self.pos_map[seg_node.pos] = [seg_node]

        # For the segments with duplicate ordinals, adjust the path to be unique
        for ord1 in sorted(self.pos_map):
            if len(self.pos_map[ord1]) > 1:
                for seg_node in [n for n in self.pos_map[ord1] if n.is_segment()]:
                    id_elem = seg_node.guess_unique_key_id_element()
                    if id_elem is not None:
                        seg_node.path = seg_node.path + '[' + id_elem.valid_codes[0] + ']'
        
    def debug_print(self):
        sys.stdout.write(self.__repr__())
        for ord1 in sorted(self.pos_map):
            for node in self.pos_map[ord1]:
                node.debug_print()

    def __len__(self):
        i = 0
        for ord1 in sorted(self.pos_map):
            i += len(self.pos_map[ord1])
        return i

    def __repr__(self):
        """
        @rtype: string
        """
        out = ''
        if self.id: 
            out += 'LOOP %s' % (self.id)
        if self.name: 
            out += '  "%s"' % (self.name)
        if self.usage: 
            out += '  usage: %s' % (self.usage)
        if self.pos: 
            out += '  pos: %s' % (self.pos)
        if self.repeat: 
            out += '  repeat: %s' % (self.repeat)
        out += '\n'
        return out

    def get_max_repeat(self):
        if self.repeat is None:
            return MAXINT
        if self.repeat == '&gt;1' or self.repeat == '>1':
            return MAXINT
        return int(self.repeat)

    def get_parent(self):
        return self.parent

    def get_first_node(self):
        pos_keys = sorted(self.pos_map)
        if len(pos_keys) > 0:
            return self.pos_map[pos_keys[0]][0]
        else:
            return None

    def get_first_seg(self):
        first = self.get_first_node()
        if first.is_segment():
            return first
        else:
            return None

    def childIterator(self):
        for ord1 in sorted(self.pos_map):
            for child in self.pos_map[ord1]:
                yield child

    def getnodebypath(self, path):
        """
        @param path: remaining path to match
        @type path: string
        @return: matching node, or None is no match
        """
        pathl = path.split('/')
        if len(pathl) == 0: 
            return None
        for ord1 in sorted(self.pos_map):
            for child in self.pos_map[ord1]:
                if child.is_loop():
                    if child.id.upper() == pathl[0].upper():
                        if len(pathl) == 1:
                            return child
                        else:
                            return child.getnodebypath(string.join(pathl[1:],'/'))
                elif child.is_segment() and len(pathl) == 1:
                    if pathl[0].find('[') == -1: # No id to match
                        if pathl[0] == child.id:
                            return child
                    else:
                        seg_id = pathl[0][0:pathl[0].find('[')]
                        id_val = pathl[0][pathl[0].find('[')+1:pathl[0].find(']')]
                        if seg_id == child.id:
                            possible = child.get_unique_key_id_element(id_val)
                            if possible is not None:
                                return child
                            #if child.children[0].is_element() \
                            #    and child.children[0].get_data_type() == 'ID' \
                            #    and len(child.children[0].valid_codes) > 0 \
                            #    and id_val in child.children[0].valid_codes:
                            #    return child
                            ## Special Case for 820
                            #elif seg_id == 'ENT' and child.children[1].is_element() \
                            #    and child.children[1].get_data_type() == 'ID' \
                            #    and len(child.children[1].valid_codes) > 0 \
                            #    and id_val in child.children[1].valid_codes:
                            #    return child
                            #elif child.children[0].is_composite() \
                            #    and child.children[0].children[0].get_data_type() == 'ID' \
                            #    and len(child.children[0].children[0].valid_codes) > 0 \
                            #    and id_val in child.children[0].children[0].valid_codes:
                            #    return child
                            #elif seg_id == 'HL' and child.children[2].is_element() \
                            #    and len(child.children[2].valid_codes) > 0 \
                            #    and id_val in child.children[2].valid_codes:
                            #    return child
        raise EngineError, 'getnodebypath failed. Path "%s" not found' % path

    def getnodebypath2(self, path_str):
        """
        Try x12 path

        @param path_str: remaining path to match
        @type path_str: string
        @return: matching node, or None is no match
        """
        x12path = path.X12Path(path_str)
        if x12path.empty():
            return None
        for ord1 in sorted(self.pos_map):
            for child in self.pos_map[ord1]:
                if child.is_loop() and len(x12path.loop_list) > 0:
                    if child.id.upper() == x12path.loop_list[0].upper():
                        if len(x12path.loop_list) == 1 and x12path.seg_id is None:
                            return child
                        else:
                            return child.getnodebypath(x12path.format())
                elif child.is_segment() and len(x12path.loop_list) == 0 and x12path.seg_id is not None:
                    if x12path.id_val is None:
                        if x12path.seg_id == child.id:
                            return child
                    else:
                        seg_id = x12path.seg_id
                        id_val = x12path.id_val
                        if seg_id == child.id:
                            possible = child.get_unique_key_id_element(id_val)
                            if possible is not None:
                                return child
                            #if child.children[0].is_element() \
                            #    and child.children[0].get_data_type() == 'ID' \
                            #    and len(child.children[0].valid_codes) > 0 \
                            #    and id_val in child.children[0].valid_codes:
                            #    return child
                            # Special Case for 820
                            #elif seg_id == 'ENT' and child.children[1].is_element() \
                            #    and child.children[1].get_data_type() == 'ID' \
                            #    and len(child.children[1].valid_codes) > 0 \
                            #    and id_val in child.children[1].valid_codes:
                            #    return child
                            #elif child.children[0].is_composite() \
                            #    and child.children[0].children[0].get_data_type() == 'ID' \
                            #    and len(child.children[0].children[0].valid_codes) > 0 \
                            #    and id_val in child.children[0].children[0].valid_codes:
                            #    return child
                            #elif seg_id == 'HL' and child.children[2].is_element() \
                            #    and len(child.children[2].valid_codes) > 0 \
                            #    and id_val in child.children[2].valid_codes:
                            #    return child
        raise EngineError, 'getnodebypath failed. Path "%s" not found' % path_str

    def get_child_count(self):
        return self.__len__()

    def get_child_node_by_idx(self, idx):
        """
        @param idx: zero based
        """
        raise EngineError, 'loop_if.get_child_node_by_idx is not a valid call'
            
    def get_seg_count(self):
        """
        @return: Number of child segments
        @rtype: integer
        """
        i = 0
        for ord1 in sorted(self.pos_map):
            for child in self.pos_map[ord1]:
                if child.is_segment():
                    i += 1
        return i

    def is_loop(self):
        """
        @rtype: boolean
        """
        return True

    def is_match(self, seg_data):
        """
        @type seg_data: L{segment<segment.Segment>}
        @return: Is the segment a match to this loop?
        @rtype: boolean
        """
        pos_keys = sorted(self.pos_map)
        child = self.pos_map[pos_keys[0]][0]
        if child.is_loop():
            return child.is_match(seg_data)
        elif child.is_segment():
            if child.is_match(seg_data):
                return True
            else:
                return False # seg does not match the first segment in loop, so not valid
        else:
            return False

    def get_child_seg_node(self, seg_data):
        """
        Return the child segment matching the segment data
        """
        for child in self.childIterator():
            if child.is_segment() and child.is_match(seg_data):
                return child
        return None

    def get_child_loop_node(self, seg_data):
        """
        Return the child segment matching the segment data
        """
        for child in self.childIterator():
            if child.is_loop() and child.is_match(seg_data):
                return child
        return None

    def get_cur_count(self):
        """
        @return: current count
        @rtype: int
        """
        return self.cur_count
        
    def incr_cur_count(self):
        self.cur_count += 1

    def reset_child_count(self):
        """
        Set cur_count of child nodes to zero
        """
        for ord1 in sorted(self.pos_map):
            for child in self.pos_map[ord1]:
                child.reset_cur_count()

    def reset_cur_count(self):
        """
        Set cur_count of node and child nodes to zero
        """
        self.cur_count = 0
        self.reset_child_count()

    def set_cur_count(self, ct):
        self.cur_count = ct

    def get_counts_list(self, ct_list):
        """
        Build a list of (path, ct) of the current node and parents
        Gets the node counts to apply to another map
        @param ct_list: List to append to
        @type ct_list: list[(string, int)]
        """
        my_ct = (self.get_path(), self.cur_count)
        ct_list.append(my_ct)
        if not self.parent.is_map_root():
            self.parent.get_counts_list(ct_list)
        return True

    def loop_segment_iterator(self):
        yield self
        for ord1 in sorted(self.pos_map):
            for child in self.pos_map[ord1]:
                if child.is_loop() or child.is_segment():
                    for c in child.loop_segment_iterator():
                        yield c

############################################################
# Segment Interface
############################################################
class segment_if(x12_node):
    """
    Segment Interface
    """
    def __init__(self, root, parent, elem):
        """
        @param parent: parent node 
        """

        x12_node.__init__(self)
        self.root = root
        self.parent = parent
        self.children = []
        self.path = ''
        self.base_name = 'segment'
        self.cur_count = 0
        self.syntax = []

        self.id = elem.get('xid')
        self.path = self.id
        self.type = elem.get('type')

        self.name = elem.findtext('name')
        self.end_tag = elem.findtext('end_tag')
        self.usage = elem.findtext('usage')
        self.pos = int(elem.findtext('pos'))
        self.max_use = elem.findtext('max_use')
        
        for s in elem.findall('syntax'):
            syn_list = self._split_syntax(s.text)
            if syn_list is not None:
                self.syntax.append(syn_list)
        
        for e in elem.findall('element'):
            self.children.append(element_if(self.root, self, e))

        for e in elem.findall('composite'):
            self.children.append(composite_if(self.root, self, e))
        
    def debug_print(self):
        sys.stdout.write(self.__repr__())
        for node in self.children:
            node.debug_print()

    def __repr__(self):
        """
        @rtype: string
        """
        out = '%s "%s"' % (self.id, self.name)
        if self.usage: 
            out += '  usage: %s' % (self.usage)
        if self.pos: 
            out += '  pos: %i' % (self.pos)
        if self.max_use: 
            out += '  max_use: %s' % (self.max_use)
        out += '\n'
        return out

    def get_child_node_by_idx(self, idx):
        """
        @param idx: zero based
        """
        if idx >= len(self.children):
            return None
        else:
            m = [c for c in self.children if c.seq==idx+1]
            if len(m) == 1:
                return m[0]
            else:
                raise EngineError, 'idx %i not found in %s' % (idx, self.id)
            
    def get_max_repeat(self):
        if self.max_use is None or self.max_use == '>1':
            return MAXINT
        return int(self.max_use)
    
    def get_parent(self):
        """
        @return: ref to parent class instance
        @rtype: pyx12.x12_node
        """
        return self.parent

    def get_path(self):
        """
        @return: path - XPath style
        @rtype: string
        """
        parent_path = self.parent.get_path()
        if parent_path == '/':
            ret = '/' + self.path
        else:
            ret = parent_path + '/' + self.path
        return ret

    def is_first_seg_in_loop(self):
        """
        @rtype: boolean
        """
        if self is self.get_parent().get_first_seg():
            return True
        else:
            return False

    def is_match(self, seg):
        """
        Is data segment given a match to this segment node?
        @param seg: data segment instance
        @return: boolean
        @rtype: boolean
        """
        if seg.get_seg_id() == self.id:
            if self.children[0].is_element() \
                and self.children[0].get_data_type() == 'ID' \
                and self.children[0].usage == 'R' \
                and len(self.children[0].valid_codes) > 0 \
                and seg.get_value('01') not in self.children[0].valid_codes:
                #logger.debug('is_match: %s %s' % (seg.get_seg_id(), seg[1]), self.children[0].valid_codes)
                return False
            # Special Case for 820
            elif seg.get_seg_id() == 'ENT' \
                and self.children[1].is_element() \
                and self.children[1].get_data_type() == 'ID' \
                and len(self.children[1].valid_codes) > 0 \
                and seg.get_value('02') not in self.children[1].valid_codes:
                #logger.debug('is_match: %s %s' % (seg.get_seg_id(), seg[1]), self.children[0].valid_codes)
                return False
            elif self.children[0].is_composite() \
                and self.children[0].children[0].get_data_type() == 'ID' \
                and len(self.children[0].children[0].valid_codes) > 0 \
                and seg.get_value('01-1') not in self.children[0].children[0].valid_codes:
                return False
            elif seg.get_seg_id() == 'HL' and self.children[2].is_element() \
                and len(self.children[2].valid_codes) > 0 \
                and seg.get_value('03') not in self.children[2].valid_codes:
                return False
            else:
                return True
        else:
            return False

    def is_match_qual(self, seg_data, seg_id, qual_code):
        """
        Is segment id and qualifier a match to this segment node and to this particulary segment data?
        @param seg_data: data segment instance
        @type seg_data: L{segment<segment.Segment>}
        @param seg_id: data segment ID
        @param qual_code: an ID qualifier code
        @return: True if a match
        @rtype: boolean
        """
        if seg_id == self.id:
            if qual_code is None:
                return True
            elif self.children[0].is_element() \
                    and self.children[0].get_data_type() == 'ID' \
                    and self.children[0].usage == 'R' \
                    and len(self.children[0].valid_codes) > 0:
                if qual_code in self.children[0].valid_codes and seg_data.get_value('01') == qual_code:
                    return True
                else:
                    return False
            # Special Case for 820
            elif seg_id == 'ENT' \
                    and self.children[1].is_element() \
                    and self.children[1].get_data_type() == 'ID' \
                    and len(self.children[1].valid_codes) > 0:
                if qual_code in self.children[1].valid_codes and seg_data.get_value('02') == qual_code:
                    return True
                else:
                    return False
            elif self.children[0].is_composite() \
                    and self.children[0].children[0].get_data_type() == 'ID' \
                    and len(self.children[0].children[0].valid_codes) > 0:
                if qual_code in self.children[0].children[0].valid_codes and seg_data.get_value('01-1') == qual_code:
                    return True
                else:
                    return False
            elif seg_id == 'HL' and self.children[2].is_element() \
                    and len(self.children[2].valid_codes) > 0:
                if qual_code in self.children[2].valid_codes and seg_data.get_value('03') == qual_code:
                    return True
                else:
                    return False
            else:
                return True
        else:
            return False

    def guess_unique_key_id_element(self):
        """
        Some segments, like REF, DTP, and DTP are duplicated.  They are matched using the value of an ID element.
        Which element to use varies.  This function tries to find a good candidate.
        """
        if self.children[0].is_element() and self.children[0].get_data_type() == 'ID' and len(self.children[0].valid_codes) > 0:
            return self.children[0]
        # Special Case for 820
        elif self.id == 'ENT' and self.children[1].is_element() and self.children[1].get_data_type() == 'ID' and len(self.children[1].valid_codes) > 0:
            return self.children[1]
        elif self.children[0].is_composite() and self.children[0].children[0].get_data_type() == 'ID' and len(self.children[0].children[0].valid_codes) > 0:
            return self.children[0].children[0]
        elif self.id == 'HL' and self.children[2].is_element() and len(self.children[2].valid_codes) > 0:
            return self.children[2]
        return None

    def get_unique_key_id_element(self, id_val):
        """
        Some segments, like REF, DTP, and DTP are duplicated.  They are matched using the value of an ID element.
        Which element to use varies.  This function tries to find a good candidate, using a key value
        """

        if self.children[0].is_element() and self.children[0].get_data_type() == 'ID' \
                and len(self.children[0].valid_codes) > 0 and id_val in self.children[0].valid_codes:
            return self.children[0]
        # Special Case for 820
        elif self.id == 'ENT' and self.children[1].is_element() and self.children[1].get_data_type() == 'ID' \
                and len(self.children[1].valid_codes) > 0 and id_val in self.children[1].valid_codes:
            return self.children[1]
        elif self.children[0].is_composite() and self.children[0].children[0].get_data_type() == 'ID' \
                and len(self.children[0].children[0].valid_codes) > 0 and id_val in self.children[0].children[0].valid_codes:
            return self.children[0].children[0]
        elif self.id == 'HL' and self.children[2].is_element() and len(self.children[2].valid_codes) > 0 and id_val in self.children[2].valid_codes:
            return self.children[2]
        return None

    def is_segment(self):
        """
        @rtype: boolean
        """
        return True

    def is_valid(self, seg_data, errh):
        """
        @param seg_data: data segment instance
        @type seg_data: L{segment<segment.Segment>}
        @param errh: instance of error_handler
        @rtype: boolean
        """
        valid = True
        child_count = self.get_child_count()
        if len(seg_data) > child_count:
            #child_node = self.get_child_node_by_idx(child_count+1)
            err_str = 'Too many elements in segment "%s" (%s). Has %i, should have %i' % \
                (self.name, seg_data.get_seg_id(), len(seg_data), child_count)
            #self.logger.error(err_str)
            ref_des = '%02i' % (child_count+1)
            err_value = seg_data.get_value(ref_des)
            errh.ele_error('3', err_str, err_value, ref_des)
            valid = False

        dtype = []
        type_list = []
        for i in range(min(len(seg_data), child_count)):
            #self.logger.debug('i=%i, len(seg_data)=%i / child_count=%i' % \
            #   (i, len(seg_data), self.get_child_count()))
            child_node = self.get_child_node_by_idx(i)
            if child_node.is_composite():
                # Validate composite
                ref_des = '%02i' % (i+1)
                comp_data = seg_data.get(ref_des)
                subele_count = child_node.get_child_count()
                if seg_data.ele_len(ref_des) > subele_count and child_node.usage != 'N':
                    subele_node = child_node.get_child_node_by_idx(subele_count+1)
                    err_str = 'Too many sub-elements in composite "%s" (%s)' % \
                        (subele_node.name, subele_node.refdes)
                    err_value = seg_data.get_value(ref_des)
                    errh.ele_error('3', err_str, err_value, ref_des)
                valid &= child_node.is_valid(comp_data, errh)
            elif child_node.is_element():
                # Validate Element
                if i == 1 and seg_data.get_seg_id() == 'DTP' \
                        and seg_data.get_value('02') in ('RD8', 'D8', 'D6', 'DT', 'TM'):
                    dtype = [seg_data.get_value('02')]
                if child_node.data_ele == '1250':
                    type_list.extend(child_node.valid_codes)
                ele_data = seg_data.get('%02i' % (i+1))
                if i == 2 and seg_data.get_seg_id() == 'DTP':
                    valid &= child_node.is_valid(ele_data, errh, dtype)
                elif child_node.data_ele == '1251' and len(type_list) > 0:
                    valid &= child_node.is_valid(ele_data, errh, type_list)
                else:
                    valid &= child_node.is_valid(ele_data, errh)

        for i in range(min(len(seg_data), child_count), child_count):
            #missing required elements?
            child_node = self.get_child_node_by_idx(i)
            valid &= child_node.is_valid(None, errh)
                
        for syn in self.syntax:
            (bResult, err_str) = is_syntax_valid(seg_data, syn)
            if not bResult:
                syn_type = syn[0]
                if syn_type == 'E':
                    errh.ele_error('10', err_str, None, syn[1])
                else:
                    errh.ele_error('2', err_str, None, syn[1])
                valid &= False

        return valid

    def _split_syntax(self, syntax):
        """
        Split a Syntax string into a list
        """
        if syntax[0] not in ['P', 'R', 'C', 'L', 'E']:
            #self.logger.error('Syntax %s is not valid' % (syntax))
            return None
        syn = [syntax[0]]
        for i in range(len(syntax[1:])/2):
            syn.append(int(syntax[i*2+1:i*2+3]))
        return syn
        
    def get_cur_count(self):
        """
        @return: current count
        @rtype: int
        """
        return self.cur_count
        
    def incr_cur_count(self):
        self.cur_count += 1

    def reset_cur_count(self):
        """
        Set cur_count of node to zero
        """
        self.cur_count = 0

    def set_cur_count(self, ct):
        self.cur_count = ct

    def get_counts_list(self, ct_list):
        """
        Build a list of (path, ct) of the current node and parents
        Gets the node counts to apply to another map
        @param ct_list: List to append to
        @type ct_list: list[(string, int)]
        """
        my_ct = (self.get_path(), self.cur_count)
        ct_list.append(my_ct)
        if not self.parent.is_map_root():
            self.parent.get_counts_list(ct_list)
        return True

    def loop_segment_iterator(self):
        yield self


############################################################
# Element Interface
############################################################
class element_if(x12_node):
    """
    Element Interface
    """

    def __init__(self, root, parent, elem):
        """
        @param parent: parent node 
        """
        x12_node.__init__(self)
        self.children = []
        self.root = root
        self.parent = parent
        self.base_name = 'element'
        self.valid_codes = []
        self.external_codes = None
        self.rec = None

        self.id = elem.get('xid')
        self.refdes= self.id
        self.name = elem.findtext('name')
        self.data_ele = elem.findtext('data_ele')
        self.usage = elem.findtext('usage')
        self.seq = int(elem.findtext('seq'))
        self.path = elem.findtext('seq')

        self.res = elem.findtext('regex')
        try:
            self.rec = re.compile(self.res, re.S)
        except:
            logger.error('Element regex "%s" failed to compile' % (self.res))
        
        v = elem.find('valid_codes')
        if v:
            self.external_codes = v.get('external')
            for c in v.findall('code'):
                self.valid_codes.append(c.text)

    def debug_print(self):
        sys.stdout.write(self.__repr__())
        for node in self.children:
            node.debug_print()

    def __repr__(self):
        """
        @rtype: string
        """
        data_ele = self.root.data_elements.get_by_elem_num(self.data_ele)
        out = '%s "%s"' % (self.refdes, self.name)
        if self.data_ele: 
            out += '  data_ele: %s' % (self.data_ele)
        if self.usage: 
            out += '  usage: %s' % (self.usage)
        if self.seq: 
            out += '  seq: %i' % (self.seq)
        out += '  %s(%i, %i)' % (data_ele['data_type'], data_ele['min_len'], data_ele['max_len'])
        if self.external_codes: 
            out += '   external codes: %s' % (self.external_codes)
        out += '\n'
        return out
   
#    def __del__(self):
#        pass

    def _error(self, errh, err_str, err_cde, elem_val):
        """
        Forward the error to an error_handler
        """
        errh.ele_error(err_cde, err_str, elem_val, self.refdes) #, pos=self.seq, data_ele=self.data_ele)
        
    def _valid_code(self, code):
        """
        Verify the x12 element value is in the given list of valid codes
        @return: True if found, else False
        @rtype: boolean
        """
        #if not self.valid_codes:
        #    return True
        if code in self.valid_codes:
            return True
        return False

    def get_parent(self):
        """
        @return: ref to parent class instance
        """
        return self.parent

    def is_match(self):
        """
        @return: 
        @rtype: boolean
        """
        # match also by ID
        raise NotImplementedError, 'Override in sub-class'
        #return False

    def is_valid(self, elem, errh, type_list=[]):
        """
        Is this a valid element?

        @param elem: element instance
        @type elem: L{element<segment.Element>}
        @param errh: instance of error_handler
        @param check_dte: date string to check against (YYYYMMDD)
        @param type_list: Optional data/time type list
        @type type_list: list[string]
        @return: True if valid
        @rtype: boolean
        """
        errh.add_ele(self)

        if elem and elem.is_composite():
            err_str = 'Data element "%s" (%s) is an invalid composite' % \
                (self.name, self.refdes)
            self._error(errh, err_str, '6', elem.__repr__())
            return False

        if elem is None or elem.get_value() == '':
            if self.usage in ('N', 'S'):
                return True
            elif self.usage == 'R':
                if self.seq != 1 or not self.parent.is_composite() or self.parent.usage == 'R':
                    err_str = 'Mandatory data element "%s" (%s) is missing' % (self.name, self.refdes)
                    self._error(errh, err_str, '1', None)
                    return False
                else:
                    return True
        if self.usage == 'N' and elem.get_value() != '':
            err_str = 'Data element "%s" (%s) is marked as Not Used' % (self.name, self.refdes)
            self._error(errh, err_str, '10', None)
            return False

        elem_val = elem.get_value()
        data_ele = self.root.data_elements.get_by_elem_num(self.data_ele)
        data_type = data_ele['data_type']
        min_len = data_ele['min_len']
        max_len = data_ele['max_len']
        valid = True
# Validate based on data_elem_num
# Then, validate on more specific criteria
        if (not data_type is None) and (data_type == 'R' or data_type[0] == 'N'):
            elem_strip = string.replace(string.replace(elem_val, '-', ''), '.', '')
            if len(elem_strip) < min_len:
                err_str = 'Data element "%s" (%s) is too short: "%s" should be at least %i characters' % \
                    (self.name, self.refdes, elem_val, min_len)
                self._error(errh, err_str, '4', elem_val)
                valid = False
            if len(elem_strip) > max_len:
                err_str = 'Element "%s" (%s) is too long: "%s" should only be %i characters' % \
                    (self.name, self.refdes, elem_val, max_len)
                self._error(errh, err_str, '5', elem_val)
                valid = False
        else:
            if len(elem_val) < min_len:
                err_str = 'Data element "%s" (%s) is too short: "%s" should be at least %i characters' % \
                    (self.name, self.refdes, elem_val, min_len)
                self._error(errh, err_str, '4', elem_val)
                valid = False
            if len(elem_val) > max_len:
                err_str = 'Element "%s" (%s) is too long: "%s" should only be %i characters' % \
                    (self.name, self.refdes, elem_val, max_len)
                self._error(errh, err_str, '5', elem_val)
                valid = False

        if data_type in ['AN', 'ID'] and elem_val[-1] == ' ':
            if len(elem_val.rstrip()) >= min_len:
                err_str = 'Element "%s" (%s) has unnecessary trailing spaces. (%s)' % \
                    (self.name, self.refdes, elem_val)
                self._error(errh, err_str, '6', elem_val)
                valid = False
            
        if not self._is_valid_code(elem_val, errh):
            valid = False
        if not validation.IsValidDataType(elem_val, data_type, self.root.param.get('charset'), self.root.icvn):
            if data_type in ('RD8', 'DT', 'D8', 'D6'):
                err_str = 'Data element "%s" (%s) contains an invalid date (%s)' % \
                    (self.name, self.refdes, elem_val)
                self._error(errh, err_str, '8', elem_val)
                valid = False
            elif data_type == 'TM':
                err_str = 'Data element "%s" (%s) contains an invalid time (%s)' % \
                    (self.name, self.refdes, elem_val)
                self._error(errh, err_str, '9', elem_val)
                valid = False
            else:
                err_str = 'Data element "%s" (%s) is type %s, contains an invalid character(%s)' % \
                    (self.name, self.refdes, data_type, elem_val)
                self._error(errh, err_str, '6', elem_val)
                valid = False
        if len(type_list) > 0:
            valid_type = False
            for dtype in type_list:
                valid_type |= validation.IsValidDataType(elem_val, dtype, self.root.param.get('charset'))
            if not valid_type:
                if 'TM' in type_list:
                    err_str = 'Data element "%s" (%s) contains an invalid time (%s)' % \
                        (self.name, self.refdes, elem_val)
                    self._error(errh, err_str, '9', elem_val)
                elif 'RD8' in type_list or 'DT' in type_list or 'D8' in type_list or 'D6' in type_list:
                    err_str = 'Data element "%s" (%s) contains an invalid date (%s)' % \
                        (self.name, self.refdes, elem_val)
                    self._error(errh, err_str, '8', elem_val)
                valid = False
        if self.rec:
            m = self.rec.search(elem_val)
            if not m:
                err_str = 'Data element "%s" with a value of (%s)' % \
                    (self.name, elem_val)
                err_str += ' failed to match the regular expression "%s"' % (self.res)
                self._error(errh, err_str, '7', elem_val)
                valid = False
        return valid

    def _is_valid_code(self, elem_val, errh):
        """
        @rtype: boolean
        """
        bValidCode = False
        if len(self.valid_codes) == 0 and self.external_codes is None:
            bValidCode = True
        if elem_val in self.valid_codes:
            bValidCode = True
        if self.external_codes is not None and \
            self.root.ext_codes.isValid(self.external_codes, elem_val):
            bValidCode = True
        if not bValidCode:
            err_str = '(%s) is not a valid code for %s (%s)' % (elem_val, self.name, self.refdes)
            self._error(errh, err_str, '7', elem_val)
            return False
        return True
        
    def get_data_type(self):
        """
        """
        data_ele = self.root.data_elements.get_by_elem_num(self.data_ele)
        return data_ele['data_type']

    def get_seg_count(self):
        """
        """
        pass

    def is_element(self):
        """
        @rtype: boolean
        """
        return True


############################################################
# Composite Interface
############################################################
class composite_if(x12_node):
    """
    Composite Node Interface
    """
    def __init__(self, root, parent, elem):
        """
        Get the values for this composite
        @param parent: parent node 
        """
        x12_node.__init__(self)

        self.children = []
        self.root = root
        self.parent = parent
        self.path = ''
        self.base_name = 'composite'

        self.name = elem.findtext('name')
        self.data_ele = elem.findtext('data_ele')
        self.usage = elem.findtext('usage')
        self.seq = int(elem.findtext('seq'))
        self.refdes = elem.findtext('refdes')
        
        for e in elem.findall('element'):
            self.children.append(element_if(self.root, self, e))

    def _error(self, errh, err_str, err_cde, elem_val):
        """
        Forward the error to an error_handler
        """
        errh.ele_error(err_cde, err_str, elem_val, self.refdes)
            #, pos=self.seq, data_ele=self.data_ele)
        
    def debug_print(self):
        sys.stdout.write(self.__repr__())
        for node in self.children:
            node.debug_print()

    def __repr__(self):
        """
        @rtype: string
        """
        out = '%s "%s"' % (self.id, self.name)
        if self.usage: 
            out += '  usage %s' % (self.usage)
        if self.seq: 
            out += '  seq %i' % (self.seq)
        if self.refdes: 
            out += '  refdes %s' % (self.refdes)
        out += '\n'
        return out

    def xml(self):
        """
        Sends an xml representation of the composite to stdout
        """
        sys.stdout.write('<composite>\n')
        for sub_elem in self.children:
            sub_elem.xml()
        sys.stdout.write('</composite>\n')

    def is_valid(self, comp_data, errh):
        """
        Validates the composite
        @param comp_data: data composite instance, has multiple values
        @param errh: instance of error_handler
        @rtype: boolean
        """
        valid = True
        if (comp_data is None or comp_data.is_empty()) and self.usage in ('N', 'S'):
            return True

        if self.usage == 'R':
            good_flag = False
            for sub_ele in comp_data:
                if sub_ele is not None and len(sub_ele.get_value()) > 0:
                    good_flag = True
                    break
            if not good_flag:
                err_str = 'At least one component of composite "%s" (%s) is required' % \
                    (self.name, self.refdes)
                errh.ele_error('2', err_str, None, self.refdes)
                return False

        if self.usage == 'N' and not comp_data.is_empty():
            err_str = 'Composite "%s" (%s) is marked as Not Used' % (self.name, self.refdes)
            errh.ele_error('5', err_str, None, self.refdes)
            return False

        #try:
        #    a = len(comp_data)
        #except:
        if len(comp_data) > self.get_child_count():
            err_str = 'Too many sub-elements in composite "%s" (%s)' % (self.name, self.refdes)
            errh.ele_error('3', err_str, None, self.refdes)
            valid = False
        for i in range(min(len(comp_data), self.get_child_count())):
            valid &= self.get_child_node_by_idx(i).is_valid(comp_data[i], errh)
        for i in range(min(len(comp_data), self.get_child_count()), \
                self.get_child_count()): 
            if i < self.get_child_count():
                #Check missing required elements
                valid &= self.get_child_node_by_idx(i).is_valid(None, errh)
        return valid

    def is_composite(self):
        """
        @rtype: boolean
        """
        return True


def load_map_file(map_file, param, xslt_files = []):
    """
    Create the map object from a file
    @param map_file: absolute path for file
    @type map_file: string
    @param xslt_files: deprecated: list of absolute paths of xsl files
    @type xslt_files: list[string]
    @rtype: pyx12.map_if
    """
    logger = logging.getLogger('pyx12')
    map_path = param.get('map_path')
    map_full = os.path.join(map_path, map_file)
    imap = None
    try:
        logger.debug('Create map from %s' % (map_full))
        etree = et.parse(map_full)
        imap = map_if(etree.getroot(), param)
    except AssertionError:
        logger.error('Load of map file failed: %s' % (map_full))
        raise
    except:
        raise
        raise EngineError, 'Load of map file failed: %s' % (map_full)
    return imap
