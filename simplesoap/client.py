import lxml.etree, lxml.builder, requests, hashlib, os, decimal, dateutil.relativedelta, dateutil.parser, datetime, collections, re, itertools, reprlib, copy, textwrap, functools

STRICT_MODE = True

class Client(object):
    def __init__(self, wsdls):
        self._wsdls = wsdls
        if isinstance(wsdls, str):
            wsdls = [wsdls]
        xmls = []
        for wsdl in wsdls:
            xmls.append(WsdlParser.get_wsdl_xml(wsdl))
        soap_calls = WsdlParser.get_soap_calls(xmls)
        for call in soap_calls:
            setattr(self, call.name, call)
        xmls
    
    def __str__(self):
        parts = ['SOAP client, available actions:']
        calls = sorted(call.name for call in self.__dict__.values() if isinstance(call, SoapCall))
        parts.extend(calls)
        return '\n  '.join(parts)
    
    def __repr__(self):
        return 'Client(wsdls={})'.format(self._wsdls)

class SoapCall(object):
    name = ''
    url = ''
    SOAPAction = ''
    input_header = None
    input_body = None
    output_header = None
    output_body = None
    
    # todo
    def __call__(self, header=None, body=None, **kwargs):
        input_header = copy.deepcopy(self.input_header)
        input_body = copy.deepcopy(self.input_body)
        
        if input_header:
            input_header.update_over(None, header)
        elif header:
            raise ValueError('No header can be parsed from the WSDL; give me a header!')
        
        if input_body:
            input_body.update_over(None, body)
        elif body:
            raise ValueError('No body can be parsed from the WSDL; give me a body!')
        
        for k, v in kwargs.items():
            # todo
            pass
        
        soap_envelope = lxml.builder.ElementMaker(namespace=SOAP.namespaces['soapenv'], nsmap=SOAP.namespaces)('Envelope')
        if input_header:
            soap_envelope.append(input_header.xml(root='Header', nsmap=SOAP.namespaces))
        if input_body:
            soap_envelope.append(input_body.xml(root='Body', nsmap=SOAP.namespaces))
        
        body = lxml.etree.tostring(soap_envelope, xml_declaration=True, encoding='UTF-8')
        
        response = requests.post(url=self.url, headers=self.http_headers, body=body)
        
        response.raise_for_status()
        
        response_xml = lxml.etree.XML(response.content)
        
        # todo: make it a dict
        return response_xml
    
    @property
    def http_headers(self):
        return {'content-type': 'text/xml; charset=utf-8',
                'SOAPAction': self.SOAPAction}
    
    def __repr__(self):
        # todo
        return object.__repr__(self)
    
    def __str__(self):
        # todo
        return object.__str__(self)

class OrderedSet(collections.OrderedDict):
    def add(self, key):
        self[key] = True
    def extend(self, keys):
        for key in keys:
            self.add(key)
    def remove(self, key):
        self.pop(key, None)
    @reprlib.recursive_repr()
    def __repr__(self):
        return '%s(%r)' % (self.__class__.__name__, list(self.keys()))

class OrderedDefaultDict(collections.OrderedDict):
    def __init__(self, keyfunc, *args, **kwargs):
        self.keyfunc = keyfunc
        super().__init__(*args, **kwargs)
    def __missing__(self, key):
        self[key] = self.keyfunc()
        return self[key]

class Restriction(object):
    minExclusive = None
    minInclusive = None
    maxExclusive = None
    maxInclusive = None
    totalDigits = None
    fractionDigits = None
    length = None
    minLength = None
    maxLength = None
    enumeration = None
    whiteSpace = None
    pattern = None
    custom = None
    minOccurs = None
    maxOccurs = None
    nillable = False
    use = None
    choices = None
    
    def __init__(self, **kwargs):
        self.update(kwargs)
        
    def update(self, kwargs):
        for k, v in kwargs.items():
            if k not in Restriction.__dict__:
                continue
            try:
                v = int(v)
            except (TypeError, ValueError):
                pass
            setattr(self, k, v)
    
    @property
    def required(self):
        if self.length is not None and self.length > 0:
            return True
        if self.minLength is not None and self.minLength > 0:
            return True
        if self.minOccurs is not None and self.minOccurs > 0:
            return True
        if self.use == 'required':
            return True
        return False
    
    def __repr__(self):
        substrings = []
        if self.minExclusive is not None:
            substrings.append('value > {}'.format(self.minExclusive))
        if self.minInclusive is not None:
            substrings.append('value >= {}'.format(self.minInclusive))
        if self.maxExclusive is not None:
            substrings.append('value < {}'.format(self.maxExclusive))
        if self.maxInclusive is not None:
            substrings.append('value <= {}'.format(self.maxInclusive))
        if self.totalDigits is not None:
            substrings.append('str(value) must have <= {} digits'.format(self.totalDigits))
        if self.fractionDigits is not None:
            substrings.append('str(value) must have <= {} digits after the decimal point'.format(self.fractionDigits))
        if self.length is not None:
            substrings.append('len(value) == {}'.format(self.length))
        if self.minLength is not None:
            substrings.append('len(value) >= {}'.format(self.minLength))
        if self.maxLength is not None:
            substrings.append('len(value) <= {}'.format(self.maxLength))
        if self.enumeration is not None:
            substrings.append('value in {}'.format(self.enumeration))
        if self.whiteSpace is not None:
            # we don't care about this
            pass
        if self.pattern is not None:
            substrings.append('re.match("{}", value)'.format('|'.join(self.pattern)))
        if self.custom is not None:
            substrings.append(self.custom)
        if self.minOccurs is not None and self.minOccurs > 0:
            substrings.append('at least {} are required'.format(self.minOccurs))
        if self.maxOccurs is not None and self.maxOccurs != 'unbounded':
            substrings.append('at most {} are allowed'.format(self.maxOccurs))
        if self.nillable:
            substrings.append('value may not be None')
        if self.use is not None:
            if self.use == 'optional':
                pass
            elif self.use == 'prohibited':
                pass
            elif self.use == 'required':
                pass
        if self.choices is not None:
            substrings.append('only one of [{}] is allowed'.format(', '.join(repr(c) for c in self.choices)))
        
        return ', '.join(substrings).strip(', ')

class Empty(Exception):
    pass

class Leaf(object):
    _sentinel = object()
    
    type = type('UNKNOWN', (object,), {})
    value = _sentinel
    default = _sentinel
    documentation = ''
    restriction = None
    
    def __init__(self, type=None, default=_sentinel, documentation='', restriction=None):
        self.type = type or Leaf.type
        self.default = default
        self.documentation = documentation
        self.restriction = restriction
    
    @property
    def required(self):
        if self.restriction is not None:
            return self.restriction.required
        return False
    
    def __repr__(self):
        substrings = [repr(self.default) if self.default is not self._sentinel else '...', ', #']
        if self.required:
            substrings.append('REQUIRED')
        else:
            substrings.append('(optional)')
        substrings.append(repr(self.type))
        if self.default is not self._sentinel:
            substrings.append('| Default: {}'.format(repr(self.default)))
        if self.restriction and repr(self.restriction):
            substrings.append('| Restrictions: {}'.format(repr(self.restriction)))
        if self.documentation:
            pass
        
        return ' '.join(substrings)
    
    @property
    def xml(self):
        if self.value is not self._sentinel:
            return self._format(self.value)
        if self.default is not self._sentinel:
            return self._format(self.default)
        raise Empty
    
    @staticmethod
    def _format(value):
        formatter = SOAP.formatters[type(value)]
        formatted_value = formatter(value)
        if formatted_value is None:
            return ''
        return formatted_value
    
    # todo
    def __deepcopy__(self, memo):
        pass

class Node(collections.OrderedDict):
    restriction = None
    base = None
    
    def __init__(self, restriction, *args, **kwargs):
        self.restriction = restriction or Restriction()
        super().__init__(*args, **kwargs)
    
    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            if self.base is not None:
                return self.base[key]
            raise
    
    def keys(self):
        keys = OrderedSet()
        if self.base is not None:
            keys.extend(self.base)
        keys.extend(self)
        return keys
    
    def update_over(self, other_k, other_v):
        if isinstance(other_v, str):
            self[other_k]
            pass
        if isinstance(other_v, collections.abc.Mapping):
            pass
        if isinstance(other_v, collections.abc.Iterable):
            pass
        for k,v in other.items():
            existing = self.get(k)
            if isinstance(existing, Node):
                existing.update_over(v)
            elif isinstance(existing, Leaf):
                self[k] = v

    def xml(self, root=None, nsmap=None):
        E = lxml.builder.ElementMaker(namespace=self.get('#namespace'), nsmap=nsmap)
        elem = E(root)
        for k in self.keys():
            v = self[k]
            try:
                if k == '#text':
                    elem.text = v.xml
                elif k.startswith('#'):
                    pass
                elif k.startswith('@'):
                    elem.attrib[k[1:]] = v.xml
                else:
                    if isinstance(v, list):
                        vs = v
                    else:
                        vs = [v]
                    for v in vs:
                        val = v.xml(root=k, nsmap=nsmap)
                        if val is None:
                            elem.attrib['{%s}%s'%(SOAP.namespaces['xsi'], 'nil')] = 'true'
                        else:
                            elem.append(val)
            except Empty:
                continue
        if not len(elem) and not elem.attrib and not elem.text:
            raise Empty
        return elem
    
    _f = collections.defaultdict(lambda : '%s: %s,', {
        Leaf: '%s: %s',
        list: '%s: [\n%s\n],',
        })
    def __repr__(self):
        if False and isinstance(self.base, Leaf):
            body = repr(self.base)
            if self.restriction and repr(self.restriction):
                body = body + ' | Additional restrictions: {}'.format(repr(self.restriction))
            return body
        keys = sorted(self.keys(), key=lambda item: (item.startswith('#'), item.startswith('@')), reverse=True)
        if keys == ['#text']:
            n = Leaf(type=self['#text'].type)
            n.restriction = self.restriction
            return repr(n)
        body = []
        for k in keys:
            v = self[k]
            formatter = self._f[type(v)]
            formatted_kv = []
            if isinstance(v, list):
                v = v[0]
                repr_v = repr(v)
                repr_v = textwrap.indent('%s,\n...' % repr_v, prefix='    ')
            else:
                repr_v = repr(v)
            if isinstance(v, Node) and v.restriction is not None and len(repr_v.splitlines()) > 1:
                if v.restriction.required:
                    formatted_kv.append('# REQUIRED')
                else:
                    formatted_kv.append('# (optional)')
                if v.restriction.choices: # todo: move this to node restriction formatting
                    max_count = 1 if v.restriction.maxOccurs is None else v.restriction.maxOccurs
                    min_count = 1 if v.restriction.minOccurs is None else v.restriction.minOccurs
                    if max_count == min_count:
                        formatted_kv.append('# only %s of a subset of %s may appear' % (max_count, v.restriction.choices))
                    else:
                        formatted_kv.append('# between %s and %s items of a subset of %s may appear' % (min_count, max_count, v.restriction.choices))
                restriction = repr(v.restriction)
                if restriction:
                    formatted_kv.append('# %s' % restriction)
            formatted_kv.append(formatter % (repr(k), repr_v))
            body.extend(formatted_kv)
        return '{\n%s\n}' % textwrap.indent('\n'.join(body), prefix='    ')
    
    # todo
    def __deepcopy__(self, memo):
        pass

class SOAP(object):
    types = {
        '{http://www.w3.org/2001/XMLSchema}string': str,
        '{http://www.w3.org/2001/XMLSchema}boolean': bool,
        '{http://www.w3.org/2001/XMLSchema}decimal': decimal.Decimal,
        '{http://www.w3.org/2001/XMLSchema}float': float,
        '{http://www.w3.org/2001/XMLSchema}double': float,
        '{http://www.w3.org/2001/XMLSchema}duration': dateutil.relativedelta.relativedelta,
        '{http://www.w3.org/2001/XMLSchema}dateTime': datetime.datetime,
        '{http://www.w3.org/2001/XMLSchema}time': datetime.time,
        '{http://www.w3.org/2001/XMLSchema}date': datetime.date,
        '{http://www.w3.org/2001/XMLSchema}integer': int,
        '{http://www.w3.org/2001/XMLSchema}byte': Leaf(type=int, restriction=Restriction(minInclusive=0, maxExclusivee=2**8)),
        '{http://www.w3.org/2001/XMLSchema}short': Leaf(type=int, restriction=Restriction(minInclusive=0, maxExclusivee=2**16)),
        '{http://www.w3.org/2001/XMLSchema}int': Leaf(type=int, restriction=Restriction(minInclusive=0, maxExclusivee=2**32)),
        '{http://www.w3.org/2001/XMLSchema}long': Leaf(type=int, restriction=Restriction(minInclusive=0, maxExclusivee=2**64)),
        '{http://www.w3.org/2001/XMLSchema}unsignedByte': Leaf(type=int, restriction=Restriction(minInclusive=-2**7, maxInclusive=2**7)),
        '{http://www.w3.org/2001/XMLSchema}unsignedShort': Leaf(type=int, restriction=Restriction(minInclusive=-2**15, maxInclusive=2**15)),
        '{http://www.w3.org/2001/XMLSchema}unsignedInt': Leaf(type=int, restriction=Restriction(minInclusive=-2**31, maxInclusive=2**31)),
        '{http://www.w3.org/2001/XMLSchema}unsignedLong': Leaf(type=int, restriction=Restriction(minInclusive=-2**63, maxInclusive=2**63)),
        '{http://www.w3.org/2001/XMLSchema}negativeInteger': Leaf(type=int, restriction=Restriction(maxExclusive=0)),
        '{http://www.w3.org/2001/XMLSchema}positiveInteger': Leaf(type=int, restriction=Restriction(minExclusive=0)),
        '{http://www.w3.org/2001/XMLSchema}nonNegativeInteger': Leaf(type=int, restriction=Restriction(minInclusive=0)),
        '{http://www.w3.org/2001/XMLSchema}nonPositiveInteger': Leaf(type=int, restriction=Restriction(maxInclusive=0)),
        '{http://www.w3.org/2001/XMLSchema}anyURI': Leaf(type=str, restriction=Restriction(custom='value must be a valid URI')),
        '{http://www.w3.org/2001/XMLSchema}language': Leaf(type=str, restriction=Restriction(custom='value must be a language according to RFC 1766', pattern=['([a-zA-Z]{2}|[iI]-[a-zA-Z]+|[xX]-[a-zA-Z]{1,8})(-[a-zA-Z]{1,8})*'])),
        }
    types = {k:v if isinstance(v, Leaf) else Leaf(type=v) for k,v in types.items()}
    
    @staticmethod
    def _format_relativedelta(v):
        s = 'P{years}Y{months}M{days}DT{hours}H{minutes}M{seconds}S'.format(**v.__dict__)
        if '-' in s:
            # todo: handle this correctly
            s = s.replace('-', '')
            s = '-' + s
        return s
    formatters = collections.defaultdict(lambda: str, {
        type(''): str,
        bool: lambda v: 'true' if v else 'false',
        type(None): lambda v: None,
        datetime.date: datetime.date.isoformat,
        datetime.time: lambda v: re.sub(r'\.\d+(\+|Z|$)', r'\1', v.isoformat()),
        datetime.datetime: lambda v: re.sub(r'\.\d+(\+|Z|$)', r'\1', v.isoformat()),
        type(lambda : None): lambda v: SOAP.formatters[type(v())](v()),
        type(repr): lambda v: SOAP.formatters[type(v())](v()),
        dateutil.relativedelta.relativedelta: _format_relativedelta,
        list: lambda v: ' '.join(SOAP.formatters[type(item)](item) for item in v),
    })
    
    @staticmethod
    def _parse_relativedelta(v):
        kwargs = re.search('(?P<negative>-)?P'
                           '(?P<years>\d+Y)?'
                           '(?P<months>\d+M)?'
                           '(?P<days>\d+D)?'
                           'T?'
                           '(?P<hours>\d+H)?'
                           '(?P<minutes>\d+M)?'
                           '(?P<seconds>\d+S)?', 
                           v).groupdict('0')
        negative = kwargs.pop('negative')
        kwargs = {k:int(re.sub('\D', '', v)) for k,v in kwargs.items()}
        rd = dateutil.relativedelta.relativedelta(**kwargs)
        if negative != '0':
            return -rd
        return rd
    @staticmethod
    def _parse_time(val):
        val = dateutil.parser.parse(val)
        return val.time().replace(tzinfo=val.tzinfo)
    @staticmethod
    def _parse_bool(val):
        if val == 'false':
            return False
        elif val == 'true':
            return True
        else:
            raise ValueError('{} not a boolean'.format(val))
    parsers = collections.defaultdict(lambda : str, {
        '{http://www.w3.org/2001/XMLSchema}string': str,
        '{http://www.w3.org/2001/XMLSchema}boolean': _parse_bool,
        '{http://www.w3.org/2001/XMLSchema}decimal': decimal.Decimal,
        '{http://www.w3.org/2001/XMLSchema}float': float,
        '{http://www.w3.org/2001/XMLSchema}double': float,
        '{http://www.w3.org/2001/XMLSchema}duration': _parse_relativedelta,
        '{http://www.w3.org/2001/XMLSchema}dateTime': dateutil.parser.parse,
        '{http://www.w3.org/2001/XMLSchema}time': _parse_time,
        '{http://www.w3.org/2001/XMLSchema}date': lambda v: dateutil.parser.parse(v).date(),
        '{http://www.w3.org/2001/XMLSchema}integer': int,
        '{http://www.w3.org/2001/XMLSchema}byte': int,
        '{http://www.w3.org/2001/XMLSchema}short': int,
        '{http://www.w3.org/2001/XMLSchema}int': int,
        '{http://www.w3.org/2001/XMLSchema}long': int,
        '{http://www.w3.org/2001/XMLSchema}unsignedByte': int,
        '{http://www.w3.org/2001/XMLSchema}unsignedShort': int,
        '{http://www.w3.org/2001/XMLSchema}unsignedInt': int,
        '{http://www.w3.org/2001/XMLSchema}unsignedLong': int,
        '{http://www.w3.org/2001/XMLSchema}negativeInteger': int,
        '{http://www.w3.org/2001/XMLSchema}positiveInteger': int,
        '{http://www.w3.org/2001/XMLSchema}nonNegativeInteger': int,
        '{http://www.w3.org/2001/XMLSchema}nonPositiveInteger': int,
        '{http://www.w3.org/2001/XMLSchema}anyURI': str,
        '{http://www.w3.org/2001/XMLSchema}language': str,
    })
    
    # todo
    @staticmethod
    def parse(xml, type_tree):
        return {}

    namespaces = {'wsdl': 'http://schemas.xmlsoap.org/wsdl/',
                  'soap': 'http://schemas.xmlsoap.org/wsdl/soap/',
                  'soap12': 'http://schemas.xmlsoap.org/wsdl/soap12/',
                  'http': 'http://schemas.xmlsoap.org/wsdl/http/',
                  'mime': 'http://schemas.xmlsoap.org/wsdl/mime/',
                  'soapenc': 'http://schemas.xmlsoap.org/soap/encoding/',
                  'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
                  'xsi': 'http://www.w3.org/2000/10/XMLSchema-instance ',
                  'xsd': 'http://www.w3.org/2000/10/XMLSchema',
                  'xs': 'http://www.w3.org/2001/XMLSchema',
                  }

class XML(object):
    @staticmethod
    def findall(xmls=None, xpath=None, use_ns=False):
        elems = OrderedSet()
        for xml in xmls:
            if use_ns:
                elems.extend(xml.xpath(xpath, namespaces=xml.nsmap))
            else:
                elems.extend(xml.xpath(xpath, namespaces=SOAP.namespaces))
        return elems
        
    @staticmethod
    def stripns(text):
        text = re.sub('^\{.*?\}', '', text, 1)
        text = re.sub('^.*?:', '', text, 1)
        return text
    
    @staticmethod
    def qualname(elem):
        name = []
        for parent in XML.findparents(elem, '*[@name]') + [elem]:
            ns = XML.findparent(elem, 'xs:schema[@targetNamespace]').attrib['targetNamespace']
            name.append('{%s}%s' % (ns, parent.attrib['name']))
        return '/'.join(name)
    
    @staticmethod
    def type(tag, nsmap=None):
        ns, name = tag.split(':')
        return '{%s}%s' % ((nsmap or SOAP.namespaces)[ns], name)
    
    @staticmethod
    def findparents(xml, xpath, use_ns=False):
        if use_ns:
            return xml.xpath('ancestor::%s'%xpath, namespaces=xml.nsmap)
        else:
            return xml.xpath('ancestor::%s'%xpath, namespaces=SOAP.namespaces)
    
    @staticmethod
    def findparent(xml, xpath, use_ns=False):
        parents = XML.findparents(xml, xpath, use_ns)
        if parents:
            return parents[-1]
        return None

class SoapMessage(object):
    parts = None
    def __getitem__(self, key):
        if not key:
            return self.parts.values()
        parts = [self.parts[subkey] for subkey in key.split()]
        return parts

class WsdlParser(object):
    cache_directory = os.path.join('/', 'tmp', 'wsdls')
    @staticmethod
    def get_wsdl_xml(wsdl_path):
        try:
            return lxml.etree.XML(open(wsdl_path, 'rb').read())
        except FileNotFoundError:
            pass
        
        try:
            return lxml.etree.XML(open(WsdlParser.get_cache_filename(wsdl_path), 'rb').read())
        except FileNotFoundError:
            req = requests.get(wsdl_path)
            req.raise_for_status()
            raw_xml = req.content
            with open(WsdlParser.get_cache_filename(wsdl_path), 'wb') as f:
                f.write(raw_xml)
            return lxml.etree.XML(raw_xml)
    
    @staticmethod
    def get_cache_filename(wsdl):
        try:
            os.mkdir(WsdlParser.cache_directory)
        except FileExistsError:
            pass
        filename = os.path.join(WsdlParser.cache_directory,
                                hashlib.sha1(wsdl.encode()).hexdigest())
        return filename
    
    @staticmethod
    def get_soap_messages(wsdls):
        soap_messages = collections.OrderedDict()
        for message in XML.findall(wsdls, 'wsdl:message'):
            soap_message = soap_messages.setdefault(message.attrib['name'], SoapMessage())
            soap_message.parts = collections.OrderedDict()
            for part in XML.findall([message], 'wsdl:part'):
                soap_message.parts[part.attrib['name']] = part.attrib['element']
        return soap_messages
    
    @staticmethod
    def build_type_tree(wsdls):
        non_type_tags = {XML.type(tag) for tag in ['wsdl:message', 'wsdl:part', 'wsdl:portType', 'wsdl:operation', 'wsdl:binding', 'wsdl:service', 'wsdl:port', 'wsdl:message', 'wsdl:input', 'wsdl:output']}
                
        type_tree = OrderedDefaultDict(keyfunc=functools.partial(Node, None))
        
        # get all the leaf types into the tree
        type_tree.update(SOAP.types)
        for elem in [e for e in XML.findall(wsdls, './/xs:simpleType') if e.tag not in non_type_tags]:
            name = elem.attrib.get('name')
            if name is not None: # has a name -> add it to the type tree root
                type_tree[XML.qualname(elem)] = Leaf()
            else: # otherwise it's defined under something -> add it under the parent
                parent = XML.findparent(elem, '*[@name]', True)
                type_tree[XML.qualname(parent)] = Leaf()
        
        # get all the node types into the tree
        for elem in [e for e in XML.findall(wsdls, './/*[@name]') if e.tag not in non_type_tags]:
            # todo: handle group + attributeGroup correctly
            
            name = elem.attrib['name']
            if elem.tag == '{http://www.w3.org/2001/XMLSchema}attribute':
                name = '@'+name
            
            if elem.attrib.get('type'):
                # has a type -> get it from the tree and add it by name
                type_ = type_tree[XML.type(elem.attrib['type'], elem.nsmap)]
            else:
                # no type -> type declaration
                type_ = None
            
            parent = XML.findparent(elem, '*[@name]', True)
            
            if parent is not None:
                if type_ is not None: # has a parent -> add it to the parent by name
                    type_tree[XML.qualname(parent)][name] = type_
                else: # or make sure it exists at the root level
                    type_tree[XML.qualname(parent)][name] = type_tree[XML.qualname(elem)]
            else:
                if type_ is not None: # no parent -> top-level element -> add it to the type tree
                    type_tree[XML.qualname(elem)] = type_
                else: # or make sure it exists in the tree
                    type_tree[XML.qualname(elem)]
        
        # todo: #namespace
        
        # todo: union type
        for elem in XML.findall(wsdls, './/xs:union'):
            pass
        
        # todo: list type
        for elem in XML.findall(wsdls, './/xs:list'):
            pass
        
        # todo: ref="..." attribute in place of name
        for elem in XML.findall(wsdls, './/*[@ref]'):
            pass
        
        # todo: qualified attribute names
        
        # todo: fixed element value
        
        # todo: minOccurs + maxOccurs
        for elem in XML.findall(wsdls, './/*[(@minOccurs or @maxOccurs) and @name]'):
            elem_restrictions = {
                'minOccurs': elem.attrib.get('minOccurs'),
                'maxOccurs': elem.attrib.get('maxOccurs'),
            }
            elem_restrictions = {k:v for k,v in elem_restrictions.items() if v is not None}
        
        # todo: handle xs:any
        
        # handle extensions
        extended_types = [e for e in XML.findall(wsdls, './/*[@base]') if e.tag not in non_type_tags]
        for elem in extended_types:
            extended_type = XML.findparent(elem, '*[@name]', True)
            base_type = type_tree[XML.type(elem.attrib['base'], elem.nsmap)]
            if isinstance(base_type, Leaf):
                type_tree[XML.qualname(extended_type)].type = base_type.type
            else:
                type_tree[XML.qualname(extended_type)].base = base_type
            
        # handle other restrictions
        for elem in XML.findall(wsdls, './/xs:restriction'):
            elem_restrictions = {k: XML.findall([elem], 'xs:%s'%k) for k in Restriction.__dict__}
            elem_restrictions = {k: [vi.attrib['value'] for vi in v] for k,v in elem_restrictions.items() if v}
            elem_restrictions = {k: v[0] if len(v) == 1 else v for k,v in elem_restrictions.items()}
            parent = XML.findparent(elem, '*[@name]', True)
            type_tree[XML.qualname(parent)].restriction = type_tree[XML.qualname(parent)].restriction or Restriction()
            type_tree[XML.qualname(parent)].restriction.update(elem_restrictions)
        
        # handle choices
        choice_elems = XML.findall(wsdls, './/xs:choice')
        for elem in choice_elems:
            parent = XML.findparent(elem, '*[@name]', True)
            type_tree[XML.qualname(parent)].restriction = type_tree[XML.qualname(parent)].restriction or Restriction()
            type_tree[XML.qualname(parent)].restriction.update({
                'choices': [e.attrib['name'] for e in XML.findall([elem], '*[@name]')],
                'minOccurs': elem.attrib.get('minOccurs', '1'),
                'maxOccurs': elem.attrib.get('maxOccurs', '1'),
            })
        
        # todo: handle defaults
        default_elems = XML.findall(wsdls, './/*[@default]')
        for elem in default_elems:
            name = elem.attrib['name']
            #if name is not None: # has a name -> add it to the type tree
            #    type_tree[XML.qualname(elem)].default = 
            #else:  # otherwise add it to the parent
            #    parent = XML.findparent(elem, '*[@name]', True)
            #    type_tree[XML.qualname(parent)].default = 
        return type_tree
    
    @staticmethod
    def get_soap_calls(wsdls):
        soap_messages = WsdlParser.get_soap_messages(wsdls)
        type_tree = WsdlParser.build_type_tree(wsdls)
        
        operations_xmls = XML.findall(wsdls, './/wsdl:operation')
        operations = {o.attrib['name'] : [] for o in operations_xmls}
        for operations_xml in operations_xmls:
            operations[operations_xml.attrib['name']].append(operations_xml)
        
        soap_calls = []
        for name, xmls in operations.items():
            soap_call = SoapCall()
            soap_calls.append(soap_call)
            
            soap_call.name = name
            
            for soapAction in XML.findall(xmls, 'soap:operation'):
                soap_call.SOAPAction = soapAction.attrib['soapAction']

            for binding in XML.findall(xmls, 'ancestor::wsdl:binding'):
                ports = XML.findall(wsdls, './/wsdl:port[contains(@binding,\':%s\')]'%binding.attrib['name'])
                addresses = XML.findall(ports, 'soap:address[@location]')
                for address in addresses:
                    soap_call.url = address.attrib['location']
            
            # normalize body / header elements with 'message' attribute
            for elem in XML.findall(xmls, 'wsdl:*[@message]'):
                message = elem.attrib['message']
                for soap_elem in XML.findall(xmls, 'wsdl:%s/soap:*'%XML.stripns(elem.tag)):
                    if 'message' not in soap_elem.attrib:
                        soap_elem.attrib['message'] = message
            
            for input_header in XML.findall(xmls, 'wsdl:input/soap:header'):
                message = XML.stripns(input_header.attrib['message'])
                part = input_header.attrib.get('part')
                for elem in soap_messages[message][part]:
                    # for now only allow one part per body / header
                    soap_call.input_header = type_tree[XML.type(elem, nsmap=input_header.nsmap)]
            
            for input_body in XML.findall(xmls, 'wsdl:input/soap:body'):
                message = XML.stripns(input_body.attrib['message'])
                parts = input_body.attrib.get('parts')
                for elem in soap_messages[message][parts]:
                    # for now only allow one part per body / header
                    soap_call.input_body = type_tree[XML.type(elem, nsmap=input_body.nsmap)]
            
            for output_header in XML.findall(xmls, 'wsdl:output/soap:header'):
                message = XML.stripns(output_header.attrib['message'])
                part = output_header.attrib.get('part')
                for elem in soap_messages[message][part]:
                    # for now only allow one part per body / header
                    soap_call.output_header = type_tree[XML.type(elem, nsmap=output_header.nsmap)]
            
            for output_body in XML.findall(xmls, 'wsdl:output/soap:body'):
                message = XML.stripns(output_body.attrib['message'])
                parts = output_body.attrib.get('parts')
                for elem in soap_messages[message][parts]:
                    # for now only allow one part per body / header
                    soap_call.output_body = type_tree[XML.type(elem, nsmap=output_body.nsmap)]
        
        return soap_calls
